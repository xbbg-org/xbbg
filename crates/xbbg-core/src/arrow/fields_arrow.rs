//! Arrow builders for field search / info.

use crate::requests::{FieldInfoRequest, FieldSearchRequest};
use crate::session::Session;
use crate::{CorrelationId, Event, EventType, Result};
use arrow::array::StringArray;
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use std::ffi::CString;
use std::sync::Arc;

/// Execute a field search request and return an Arrow batch.
///
/// Schema:
/// - field_id, field_name, field_type, description, category.
pub fn execute_field_search_arrow(
    session: &Session,
    req: &FieldSearchRequest,
) -> Result<RecordBatch> {
    req.validate()
        .map_err(|e| crate::BlpError::InvalidArgument {
            detail: e.to_string(),
        })?;

    // Open service and create request
    session.open_service("//blp/apiflds")?;
    let service = session.get_service("//blp/apiflds")?;

    let blp_request = service.create_request("FieldSearchRequest")?;

    // Set search string - Bloomberg example: request.set(k_searchSpec, "last price")
    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        let k_search_spec = CString::new("searchSpec").unwrap();
        let c_search = CString::new(req.search.as_str()).unwrap();
        let rc = blpapi_sys::blpapi_Element_setElementString(
            root_el,
            k_search_spec.as_ptr(),
            std::ptr::null(),
            c_search.as_ptr(),
        );

        if rc != 0 {
            return Err(crate::BlpError::InvalidArgument {
                detail: format!("failed to set searchSpec: rc={}", rc),
            });
        }

        // Set exclude and returnFieldDocumentation defaults
        let k_exclude = CString::new("exclude").unwrap();
        let k_return_field_documentation = CString::new("returnFieldDocumentation").unwrap();
        blpapi_sys::blpapi_Element_setElementBool(root_el, k_exclude.as_ptr(), std::ptr::null(), 0);
        blpapi_sys::blpapi_Element_setElementBool(
            root_el,
            k_return_field_documentation.as_ptr(),
            std::ptr::null(),
            1,
        );
    }

    // Send request with an explicit correlation id so we can safely multiplex
    // multiple in-flight requests on the same session.
    let cid = CorrelationId::next();
    session.send_request(&blp_request, None, Some(&cid))?;

    // Collect response data
    let mut field_ids = Vec::new();
    let mut field_names = Vec::new();
    let mut field_types = Vec::new();
    let mut descriptions = Vec::new();
    let mut categories = Vec::new();

    // Process events until we get a RESPONSE
    loop {
        let event = session.next_event(Some(60000))?; // 60s timeout
        match event.event_type() {
            EventType::Response => {
                process_field_search_response(
                    &event,
                    &cid,
                    &mut field_ids,
                    &mut field_names,
                    &mut field_types,
                    &mut descriptions,
                    &mut categories,
                )?;
                break;
            }
            EventType::PartialResponse => {
                process_field_search_response(
                    &event,
                    &cid,
                    &mut field_ids,
                    &mut field_names,
                    &mut field_types,
                    &mut descriptions,
                    &mut categories,
                )?;
                // Continue to wait for final RESPONSE
            }
            EventType::RequestStatus => {
                // Check for errors
                for msg in event.iter() {
                    if !msg.matches_correlation_id(&cid) {
                        continue;
                    }
                    let msg_type = msg.message_type();
                    if msg_type.as_str() == "RequestFailure" {
                        return Err(crate::BlpError::Internal {
                            detail: format!("Request failed: {}", msg.print_to_string()),
                        });
                    }
                }
            }
            _ => {
                // Ignore other event types
            }
        }
    }

    // Build Arrow arrays
    let schema = Arc::new(Schema::new(vec![
        Field::new("field_id", DataType::Utf8, false),
        Field::new("field_name", DataType::Utf8, true),
        Field::new("field_type", DataType::Utf8, true),
        Field::new("description", DataType::Utf8, true),
        Field::new("category", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(field_ids)),
            Arc::new(StringArray::from(field_names)),
            Arc::new(StringArray::from(field_types)),
            Arc::new(StringArray::from(descriptions)),
            Arc::new(StringArray::from(categories)),
        ],
    )
    .map_err(|e| crate::BlpError::Internal {
        detail: format!("failed to build field search RecordBatch: {e}"),
    })?;

    Ok(batch)
}

fn process_field_search_response(
    event: &Event,
    cid: &CorrelationId,
    field_ids: &mut Vec<String>,
    field_names: &mut Vec<Option<String>>,
    field_types: &mut Vec<Option<String>>,
    descriptions: &mut Vec<Option<String>>,
    categories: &mut Vec<Option<String>>,
) -> Result<()> {
    for msg in event.iter() {
        // Only process messages for our correlation id.
        if !msg.matches_correlation_id(cid) {
            continue;
        }
        let msg_type = msg.message_type();
        // Also check for alternative response types
        if msg_type.as_str() != "FieldSearchResponse" && msg_type.as_str() != "fieldResponse" {
            continue;
        }

        let root = msg.elements();
        // From raw response: fieldData[] is an array, same structure as FieldInfoResponse
        // fieldData[] = { fieldData = { id = "PR005" fieldInfo = { mnemonic = "PX_LAST" ... } } ... }
        if let Some(field_data_array) = root.get_element("fieldData") {
            let num_fields = field_data_array.num_values();
            for field_idx in 0..num_fields {
                if let Some(field_el) = field_data_array.get_value_as_element(field_idx) {
                    // Extract field ID from "id" element
                    let field_id = field_el
                        .get_element("id")
                        .and_then(|el| el.get_value_as_string(0))
                        .unwrap_or_default();

                    // Extract other fields from "fieldInfo" nested sequence
                    if let Some(field_info) = field_el.get_element("fieldInfo") {
                        field_ids.push(field_id);
                        field_names.push(
                            field_info
                                .get_element("mnemonic")
                                .and_then(|el| el.get_value_as_string(0)),
                        );
                        field_types.push(
                            field_info
                                .get_element("ftype")
                                .and_then(|el| el.get_value_as_string(0)),
                        );
                        descriptions.push(
                            field_info
                                .get_element("description")
                                .and_then(|el| el.get_value_as_string(0)),
                        );
                        categories.push(field_info.get_element("categoryName").and_then(|el| {
                            // categoryName is an array, get first value if available
                            if el.num_values() > 0 {
                                el.get_value_as_string(0)
                            } else {
                                None
                            }
                        }));
                    }
                }
            }
        }
    }
    Ok(())
}

/// Execute a field info request and return an Arrow batch.
///
/// Schema:
/// - field_id, mnemonic, ftype, description, category, plus key metadata.
pub fn execute_field_info_arrow(session: &Session, req: &FieldInfoRequest) -> Result<RecordBatch> {
    req.validate()
        .map_err(|e| crate::BlpError::InvalidArgument {
            detail: e.to_string(),
        })?;

    // Open service and create request
    session.open_service("//blp/apiflds")?;
    let service = session.get_service("//blp/apiflds")?;

    let blp_request = service.create_request("FieldInfoRequest")?;

    // Set field IDs - Bloomberg example uses "id" not "fieldIds"
    unsafe {
        let root_el = blpapi_sys::blpapi_Request_elements(blp_request.as_raw());
        // Try "id" first (as per Bloomberg examples), then "fieldIds"
        let k_id = CString::new("id").unwrap();
        let mut el_field_ids: *mut blpapi_sys::blpapi_Element_t = std::ptr::null_mut();
        let mut rc = blpapi_sys::blpapi_Element_getElement(
            root_el,
            &mut el_field_ids,
            k_id.as_ptr(),
            std::ptr::null(),
        );
        if rc != 0 || el_field_ids.is_null() {
            // Fallback to "fieldIds"
            let k_field_ids = CString::new("fieldIds").unwrap();
            rc = blpapi_sys::blpapi_Element_getElement(
                root_el,
                &mut el_field_ids,
                k_field_ids.as_ptr(),
                std::ptr::null(),
            );
        }
        if rc == 0 && !el_field_ids.is_null() {
            for field_id in &req.field_ids {
                let c_field_id = CString::new(field_id.as_str()).unwrap();
                let rc = blpapi_sys::blpapi_Element_setValueString(
                    el_field_ids,
                    c_field_id.as_ptr(),
                    blpapi_sys::BLPAPI_ELEMENT_INDEX_END as usize,
                );
                if rc != 0 {
                    return Err(crate::BlpError::InvalidArgument {
                        detail: format!("failed to add field id: {field_id}"),
                    });
                }
            }
        } else {
            return Err(crate::BlpError::InvalidArgument {
                detail: "failed to find 'id' or 'fieldIds' element in FieldInfoRequest".into(),
            });
        }
    }

    // Send request with an explicit correlation id so we can safely multiplex
    // multiple in-flight requests on the same session.
    let cid = CorrelationId::next();
    session.send_request(&blp_request, None, Some(&cid))?;

    // Collect response data
    let mut field_ids = Vec::new();
    let mut mnemonics = Vec::new();
    let mut ftypes = Vec::new();
    let mut descriptions = Vec::new();
    let mut categories = Vec::new();

    // Process events until we get a RESPONSE
    loop {
        let event = session.next_event(Some(60000))?; // 60s timeout
        match event.event_type() {
            EventType::Response => {
                process_field_info_response(
                    &event,
                    &cid,
                    &mut field_ids,
                    &mut mnemonics,
                    &mut ftypes,
                    &mut descriptions,
                    &mut categories,
                )?;
                break;
            }
            EventType::PartialResponse => {
                process_field_info_response(
                    &event,
                    &cid,
                    &mut field_ids,
                    &mut mnemonics,
                    &mut ftypes,
                    &mut descriptions,
                    &mut categories,
                )?;
                // Continue to wait for final RESPONSE
            }
            EventType::RequestStatus => {
                // Check for errors
                for msg in event.iter() {
                    if !msg.matches_correlation_id(&cid) {
                        continue;
                    }
                    let msg_type = msg.message_type();
                    if msg_type.as_str() == "RequestFailure" {
                        return Err(crate::BlpError::Internal {
                            detail: format!("Request failed: {}", msg.print_to_string()),
                        });
                    }
                }
            }
            _ => {
                // Ignore other event types
            }
        }
    }

    // Build Arrow arrays
    let schema = Arc::new(Schema::new(vec![
        Field::new("field_id", DataType::Utf8, false),
        Field::new("mnemonic", DataType::Utf8, true),
        Field::new("ftype", DataType::Utf8, true),
        Field::new("description", DataType::Utf8, true),
        Field::new("category", DataType::Utf8, true),
    ]));

    let batch = RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(field_ids)),
            Arc::new(StringArray::from(mnemonics)),
            Arc::new(StringArray::from(ftypes)),
            Arc::new(StringArray::from(descriptions)),
            Arc::new(StringArray::from(categories)),
        ],
    )
    .map_err(|e| crate::BlpError::Internal {
        detail: format!("failed to build field info RecordBatch: {e}"),
    })?;

    Ok(batch)
}

fn process_field_info_response(
    event: &Event,
    cid: &CorrelationId,
    field_ids: &mut Vec<String>,
    mnemonics: &mut Vec<Option<String>>,
    ftypes: &mut Vec<Option<String>>,
    descriptions: &mut Vec<Option<String>>,
    categories: &mut Vec<Option<String>>,
) -> Result<()> {
    for msg in event.iter() {
        // Only process messages for our correlation id.
        if !msg.matches_correlation_id(cid) {
            continue;
        }
        let msg_type = msg.message_type();
        if msg_type.as_str() != "FieldInfoResponse" && msg_type.as_str() != "fieldResponse" {
            continue;
        }

        let root = msg.elements();

        // From raw response: fieldData[] is an array
        // fieldData[] = { fieldData = { id = "DS002" fieldInfo = { mnemonic = "NAME" ... } } ... }
        if let Some(field_data_array) = root.get_element("fieldData") {
            let num_fields = field_data_array.num_values();
            for field_idx in 0..num_fields {
                if let Some(field_el) = field_data_array.get_value_as_element(field_idx) {
                    // Extract field ID from "id" element
                    let field_id = field_el
                        .get_element("id")
                        .and_then(|el| el.get_value_as_string(0))
                        .unwrap_or_default();

                    // Extract other fields from "fieldInfo" nested sequence
                    if let Some(field_info) = field_el.get_element("fieldInfo") {
                        field_ids.push(field_id);
                        mnemonics.push(
                            field_info
                                .get_element("mnemonic")
                                .and_then(|el| el.get_value_as_string(0)),
                        );
                        ftypes.push(
                            field_info
                                .get_element("ftype")
                                .and_then(|el| el.get_value_as_string(0)),
                        );
                        descriptions.push(
                            field_info
                                .get_element("description")
                                .and_then(|el| el.get_value_as_string(0)),
                        );
                        categories.push(field_info.get_element("categoryName").and_then(|el| {
                            // categoryName is an array, get first value if available
                            if el.num_values() > 0 {
                                el.get_value_as_string(0)
                            } else {
                                None
                            }
                        }));
                    }
                }
            }
        }
    }
    Ok(())
}
