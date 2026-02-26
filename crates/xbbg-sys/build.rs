#[cfg(feature = "mock")]
use bindgen::callbacks::ParseCallbacks;

#[cfg(feature = "mock")]
#[derive(Debug)]
struct RenameCallback;

#[cfg(feature = "mock")]
impl ParseCallbacks for RenameCallback {
    fn item_name(&self, original_name: &str) -> Option<String> {
        // Rename functions: datamock_Session_start -> blpapi_Session_start
        if original_name.starts_with("datamock_") {
            return Some(original_name.replace("datamock_", "blpapi_"));
        }
        // Rename constants: DATAMOCK_CORRELATION_TYPE_INT -> BLPAPI_CORRELATION_TYPE_INT
        if original_name.starts_with("DATAMOCK_") {
            return Some(original_name.replace("DATAMOCK_", "BLPAPI_"));
        }
        // Rename helpers: datamockext_cid_from_ptr -> blpapiext_cid_from_ptr
        if original_name.starts_with("datamockext_") {
            return Some(original_name.replace("datamockext_", "blpapiext_"));
        }
        None // Keep original name
    }
}

fn main() {
    // Check for mutual exclusivity at build time
    #[cfg(all(feature = "mock", feature = "live"))]
    compile_error!("Features 'mock' and 'live' are mutually exclusive");

    #[cfg(feature = "mock")]
    {
        println!("cargo:rerun-if-changed=../datamock/cpp/include/datamock/datamock_c_api.h");

        // Generate renamed bindings from datamock
        // Blocklist functions that have signature mismatches - shim will provide wrappers
        // Note: blocklist uses ORIGINAL names (before renaming)
        let bindings = bindgen::Builder::default()
            .header("../datamock/cpp/include/datamock/datamock_c_api.h")
            .parse_callbacks(Box::new(RenameCallback))
            .blocklist_function("datamock_Element_getElement")
            .blocklist_function("datamock_Element_setValueString")
            .blocklist_function("datamock_Element_setValueInt32")
            .blocklist_function("datamock_Message_elements")
            .blocklist_function("datamock_MessageIterator_create")
            .blocklist_function("datamock_Request_getElement")
            .blocklist_function("datamock_Session_create")
            .blocklist_function("datamock_Session_sendRequest")
            .blocklist_function("datamock_Session_subscribe")
            .blocklist_function("datamock_Session_unsubscribe")
            .blocklist_function("datamock_SubscriptionList_add")
            .generate()
            .expect("Unable to generate bindings");

        let out_path = std::path::PathBuf::from(std::env::var("OUT_DIR").unwrap());
        bindings
            .write_to_file(out_path.join("bindings.rs"))
            .expect("Couldn't write bindings!");
    }

    #[cfg(feature = "live")]
    {
        // No build script needed - blpapi-sys already has bindings
        println!("cargo:rerun-if-changed=build.rs");
    }
}
