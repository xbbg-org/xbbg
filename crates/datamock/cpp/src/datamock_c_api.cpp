/*
 * datamock C API implementation
 *
 * Wraps BEmu C++ classes with a C-compatible interface.
 */

// DATAMOCK_BUILDING is defined by build.rs via -D flag
#include "datamock/datamock_c_api.h"

#include "BloombergTypes/Session.h"
#include "BloombergTypes/SessionOptions.h"
#include "BloombergTypes/Service.h"
#include "BloombergTypes/Request.h"
#include "BloombergTypes/Event.h"
#include "BloombergTypes/Message.h"
#include "BloombergTypes/Element.h"
#include "BloombergTypes/Name.h"
#include "BloombergTypes/SubscriptionList.h"
#include "BloombergTypes/Subscription.h"
#include "BloombergTypes/MessageIterator.h"
#include "BloombergTypes/Datetime.h"
#include "BloombergTypes/CorrelationId.h"
#include "BloombergTypes/EventHandler.h"

#include <cstring>
#include <string>
#include <memory>
#include <iostream>

using namespace BEmu;

/* ============================================================================
 * Internal wrapper classes to hold C++ objects behind opaque handles
 * ============================================================================ */

struct datamock_SessionOptions_t {
    SessionOptions options;
};

struct datamock_Session_t {
    std::unique_ptr<Session> session;
    datamock_EventHandler_t handler;
    void* userData;
};

struct datamock_Service_t {
    Service service;
};

struct datamock_Request_t {
    Request request;
};

struct datamock_Event_t {
    Event event;
};

struct datamock_Message_t {
    Message message;
};

struct datamock_Element_t {
    Element element;
};

struct datamock_Name_t {
    Name name;
};

struct datamock_SubscriptionList_t {
    SubscriptionList list;
};

struct datamock_MessageIterator_t {
    MessageIterator iterator;
    datamock_MessageIterator_t(const Event& event) : iterator(event) {}
};

/* ============================================================================
 * Event handler bridge for async mode
 * ============================================================================ */

class CEventHandlerBridge : public EventHandler {
public:
    CEventHandlerBridge(datamock_EventHandler_t handler, datamock_Session_t* session, void* userData)
        : m_handler(handler), m_session(session), m_userData(userData) {}

    bool processEvent(const Event& event, Session* session) override {
        if (m_handler) {
            // Create a temporary wrapper for the event
            datamock_Event_t eventWrapper;
            eventWrapper.event = event;
            m_handler(&eventWrapper, m_session, m_userData);
        }
        return true;
    }

private:
    datamock_EventHandler_t m_handler;
    datamock_Session_t* m_session;
    void* m_userData;
};

/* ============================================================================
 * SessionOptions
 * ============================================================================ */

datamock_SessionOptions_t* datamock_SessionOptions_create(void) {
    return new datamock_SessionOptions_t();
}

void datamock_SessionOptions_destroy(datamock_SessionOptions_t* options) {
    delete options;
}

int datamock_SessionOptions_setServerHost(datamock_SessionOptions_t* options, const char* host) {
    if (!options || !host) return DATAMOCK_ERROR_ILLEGAL_ARG;
    options->options.setServerHost(host);
    return DATAMOCK_OK;
}

int datamock_SessionOptions_setServerPort(datamock_SessionOptions_t* options, uint16_t port) {
    if (!options) return DATAMOCK_ERROR_ILLEGAL_ARG;
    options->options.setServerPort(port);
    return DATAMOCK_OK;
}

const char* datamock_SessionOptions_serverHost(datamock_SessionOptions_t* options) {
    if (!options) return nullptr;
    return options->options.serverHost();
}

uint16_t datamock_SessionOptions_serverPort(datamock_SessionOptions_t* options) {
    if (!options) return 0;
    return options->options.serverPort();
}

/* ============================================================================
 * Session
 * ============================================================================ */

datamock_Session_t* datamock_Session_create(
    datamock_SessionOptions_t* options,
    datamock_EventHandler_t handler,
    void* userData)
{
    if (!options) return nullptr;
    
    auto* wrapper = new datamock_Session_t();
    wrapper->handler = handler;
    wrapper->userData = userData;
    
    try {
        if (handler) {
            // Async mode with event handler
            auto* bridge = new CEventHandlerBridge(handler, wrapper, userData);
            wrapper->session = std::make_unique<Session>(options->options, bridge);
        } else {
            // Sync mode
            wrapper->session = std::make_unique<Session>(options->options);
        }
    } catch (...) {
        delete wrapper;
        return nullptr;
    }
    
    return wrapper;
}

void datamock_Session_destroy(datamock_Session_t* session) {
    delete session;
}

int datamock_Session_start(datamock_Session_t* session) {
    if (!session || !session->session) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        return session->session->start() ? DATAMOCK_OK : DATAMOCK_ERROR_UNKNOWN;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_startAsync(datamock_Session_t* session) {
    if (!session || !session->session) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        return session->session->startAsync() ? DATAMOCK_OK : DATAMOCK_ERROR_UNKNOWN;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_stop(datamock_Session_t* session) {
    if (!session || !session->session) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        session->session->stop();
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_stopAsync(datamock_Session_t* session) {
    // BEmu doesn't have stopAsync, just call stop
    return datamock_Session_stop(session);
}

int datamock_Session_openService(datamock_Session_t* session, const char* uri) {
    if (!session || !session->session || !uri) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        return session->session->openService(uri) ? DATAMOCK_OK : DATAMOCK_ERROR_UNKNOWN;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_openServiceAsync(
    datamock_Session_t* session,
    const char* uri,
    datamock_CorrelationId_t* correlationId)
{
    if (!session || !session->session || !uri) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        CorrelationId cid;
        if (correlationId && correlationId->valueType == DATAMOCK_CORRELATION_TYPE_INT) {
            cid = CorrelationId(correlationId->value.intValue);
        }
        session->session->openServiceAsync(uri, cid);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_getService(
    datamock_Session_t* session,
    datamock_Service_t** service,
    const char* uri)
{
    if (!session || !session->session || !service || !uri) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *service = new datamock_Service_t();
        (*service)->service = session->session->getService(uri);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_NOT_FOUND;
    }
}

int datamock_Session_sendRequest(
    datamock_Session_t* session,
    datamock_Request_t* request,
    datamock_CorrelationId_t* correlationId,
    const char* /* requestLabel */)
{
    if (!session || !session->session || !request) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        CorrelationId cid;
        if (correlationId && correlationId->valueType == DATAMOCK_CORRELATION_TYPE_INT) {
            cid = CorrelationId(correlationId->value.intValue);
        }
        session->session->sendRequest(request->request, cid);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_nextEvent(
    datamock_Session_t* session,
    datamock_Event_t** event,
    uint32_t timeoutMs)
{
    if (!session || !session->session || !event) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *event = new datamock_Event_t();
        (*event)->event = session->session->nextEvent(static_cast<int>(timeoutMs));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_tryNextEvent(
    datamock_Session_t* session,
    datamock_Event_t** event)
{
    return datamock_Session_nextEvent(session, event, 0);
}

int datamock_Session_subscribe(
    datamock_Session_t* session,
    datamock_SubscriptionList_t* subscriptions)
{
    if (!session || !session->session || !subscriptions) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        session->session->subscribe(subscriptions->list);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_unsubscribe(
    datamock_Session_t* session,
    datamock_SubscriptionList_t* subscriptions)
{
    if (!session || !session->session || !subscriptions) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        session->session->unsubscribe(subscriptions->list);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Session_cancel(
    datamock_Session_t* session,
    datamock_CorrelationId_t* correlationIds,
    size_t numCorrelationIds)
{
    if (!session || !session->session) return DATAMOCK_ERROR_ILLEGAL_ARG;
    if (numCorrelationIds == 0) return DATAMOCK_OK;
    if (!correlationIds) return DATAMOCK_ERROR_ILLEGAL_ARG;
    
    try {
        for (size_t i = 0; i < numCorrelationIds; ++i) {
            CorrelationId cid(correlationIds[i].value.intValue);
            session->session->cancel(cid);
        }
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

/* ============================================================================
 * Service
 * ============================================================================ */

int datamock_Service_createRequest(
    datamock_Service_t* service,
    datamock_Request_t** request,
    const char* operationName)
{
    if (!service || !request || !operationName) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *request = new datamock_Request_t();
        (*request)->request = service->service.createRequest(operationName);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_NOT_FOUND;
    }
}

const char* datamock_Service_name(datamock_Service_t* service) {
    if (!service) return nullptr;
    return service->service.name();
}

/* ============================================================================
 * Request
 * ============================================================================ */

void datamock_Request_destroy(datamock_Request_t* request) {
    delete request;
}

int datamock_Request_getElement(
    datamock_Request_t* request,
    datamock_Element_t** element)
{
    if (!request || !element) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *element = new datamock_Element_t();
        // BEmu Request doesn't have asElement(), use getElement with empty name
        // This is a limitation - caller should use append/set directly
        return DATAMOCK_ERROR_NOT_FOUND;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Request_append(
    datamock_Request_t* request,
    const char* name,
    const char* value)
{
    if (!request || !name || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        request->request.append(name, value);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Request_set(
    datamock_Request_t* request,
    const char* name,
    const char* value)
{
    if (!request || !name || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        request->request.set(name, value);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Request_setInt32(
    datamock_Request_t* request,
    const char* name,
    int32_t value)
{
    if (!request || !name) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        request->request.set(name, value);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Request_setDatetime(
    datamock_Request_t* request,
    const char* name,
    const datamock_Datetime_t* value)
{
    if (!request || !name || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        // Convert C struct to BEmu Datetime
        Datetime dt(value->year, value->month, value->day, 
                    value->hours, value->minutes, value->seconds, value->milliSeconds);
        request->request.set(name, dt);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

/* ============================================================================
 * Event
 * ============================================================================ */

void datamock_Event_release(datamock_Event_t* event) {
    delete event;
}

datamock_EventType_t datamock_Event_eventType(datamock_Event_t* event) {
    if (!event) return static_cast<datamock_EventType_t>(0);
    return static_cast<datamock_EventType_t>(event->event.eventType());
}

int datamock_MessageIterator_create(
    datamock_MessageIterator_t** iterator,
    datamock_Event_t* event)
{
    if (!iterator || !event) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *iterator = new datamock_MessageIterator_t(event->event);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

void datamock_MessageIterator_destroy(datamock_MessageIterator_t* iterator) {
    delete iterator;
}

int datamock_MessageIterator_next(
    datamock_MessageIterator_t* iterator,
    datamock_Message_t** message)
{
    if (!iterator || !message) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        if (iterator->iterator.next()) {
            *message = new datamock_Message_t();
            (*message)->message = iterator->iterator.message();
            return DATAMOCK_OK;
        }
        *message = nullptr;
        return DATAMOCK_ERROR_NOT_FOUND;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

/* ============================================================================
 * Message
 * ============================================================================ */

int datamock_Message_elements(
    datamock_Message_t* message,
    datamock_Element_t** element)
{
    if (!message || !element) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *element = new datamock_Element_t();
        (*element)->element = message->message.asElement();
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Message_correlationId(
    datamock_Message_t* message,
    datamock_CorrelationId_t* correlationId,
    size_t index)
{
    if (!message || !correlationId) return DATAMOCK_ERROR_ILLEGAL_ARG;
    if (index != 0) return DATAMOCK_ERROR_NOT_FOUND; // BEmu only supports single correlation id
    try {
        CorrelationId cid = message->message.correlationId();
        correlationId->valueType = DATAMOCK_CORRELATION_TYPE_INT;
        correlationId->value.intValue = cid.asInteger();
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_NOT_FOUND;
    }
}

size_t datamock_Message_numCorrelationIds(datamock_Message_t* message) {
    if (!message) return 0;
    // BEmu Message has single correlationId, return 1
    return 1;
}

const char* datamock_Message_typeString(datamock_Message_t* message) {
    if (!message) return nullptr;
    return message->message.messageType().string();
}

const char* datamock_Message_topicName(datamock_Message_t* message) {
    if (!message) return nullptr;
    return message->message.topicName();
}

/* ============================================================================
 * Element
 * ============================================================================ */

datamock_DataType_t datamock_Element_datatype(datamock_Element_t* element) {
    if (!element) return static_cast<datamock_DataType_t>(0);
    return static_cast<datamock_DataType_t>(element->element.datatype());
}

int datamock_Element_isArray(datamock_Element_t* element) {
    if (!element) return 0;
    return element->element.isArray() ? 1 : 0;
}

int datamock_Element_isComplexType(datamock_Element_t* element) {
    if (!element) return 0;
    return element->element.isComplexType() ? 1 : 0;
}

int datamock_Element_isNull(datamock_Element_t* element) {
    if (!element) return 1;
    return element->element.isNull() ? 1 : 0;
}

size_t datamock_Element_numValues(datamock_Element_t* element) {
    if (!element) return 0;
    return element->element.numValues();
}

size_t datamock_Element_numElements(datamock_Element_t* element) {
    if (!element) return 0;
    return element->element.numElements();
}

int datamock_Element_nameString(
    datamock_Element_t* element,
    const char** name)
{
    if (!element || !name) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *name = element->element.name().string();
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_hasElement(
    datamock_Element_t* element,
    const char* name,
    datamock_Bool_t excludeNullElements)
{
    if (!element || !name) return 0;
    return element->element.hasElement(name, excludeNullElements != 0) ? 1 : 0;
}

int datamock_Element_getElement(
    datamock_Element_t* element,
    datamock_Element_t** result,
    const char* name)
{
    if (!element || !result || !name) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *result = new datamock_Element_t();
        (*result)->element = element->element.getElement(name);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_NOT_FOUND;
    }
}

int datamock_Element_getElementAt(
    datamock_Element_t* element,
    datamock_Element_t** result,
    size_t index)
{
    if (!element || !result) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *result = new datamock_Element_t();
        (*result)->element = element->element.getElement(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_NOT_FOUND;
    }
}

int datamock_Element_getValueAsBool(
    datamock_Element_t* element,
    datamock_Bool_t* value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = element->element.getValueAsBool(static_cast<int>(index)) ? 1 : 0;
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsInt32(
    datamock_Element_t* element,
    datamock_Int32_t* value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = element->element.getValueAsInt32(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsInt64(
    datamock_Element_t* element,
    datamock_Int64_t* value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = element->element.getValueAsInt64(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsFloat32(
    datamock_Element_t* element,
    datamock_Float32_t* value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = element->element.getValueAsFloat32(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsFloat64(
    datamock_Element_t* element,
    datamock_Float64_t* value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = element->element.getValueAsFloat64(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsString(
    datamock_Element_t* element,
    const char** value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = element->element.getValueAsString(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsDatetime(
    datamock_Element_t* element,
    datamock_Datetime_t* value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        Datetime dt = element->element.getValueAsDatetime(static_cast<int>(index));
        value->year = static_cast<uint16_t>(dt.year());
        value->month = static_cast<uint8_t>(dt.month());
        value->day = static_cast<uint8_t>(dt.day());
        value->hours = static_cast<uint8_t>(dt.hours());
        value->minutes = static_cast<uint8_t>(dt.minutes());
        value->seconds = static_cast<uint8_t>(dt.seconds());
        value->milliSeconds = static_cast<uint16_t>(dt.milliseconds());
        value->offset = 0;
        value->parts = DATAMOCK_DATETIME_DATE_PART | DATAMOCK_DATETIME_TIME_PART;
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_getValueAsElement(
    datamock_Element_t* element,
    datamock_Element_t** value,
    size_t index)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        *value = new datamock_Element_t();
        (*value)->element = element->element.getValueAsElement(static_cast<int>(index));
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_setValueString(
    datamock_Element_t* element,
    const char* value,
    size_t /* index */)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        element->element.setElement("value", value);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_setValueInt32(
    datamock_Element_t* element,
    datamock_Int32_t value,
    size_t /* index */)
{
    if (!element) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        element->element.setElement("value", value);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

int datamock_Element_appendValue(
    datamock_Element_t* element,
    const char* value)
{
    if (!element || !value) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        element->element.appendValue(value);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

/* ============================================================================
 * Name
 * ============================================================================ */

datamock_Name_t* datamock_Name_create(const char* nameString) {
    if (!nameString) return nullptr;
    try {
        auto* wrapper = new datamock_Name_t();
        wrapper->name = Name(nameString);
        return wrapper;
    } catch (...) {
        return nullptr;
    }
}

void datamock_Name_destroy(datamock_Name_t* name) {
    delete name;
}

const char* datamock_Name_string(datamock_Name_t* name) {
    if (!name) return nullptr;
    return name->name.string();
}

/* ============================================================================
 * SubscriptionList
 * ============================================================================ */

datamock_SubscriptionList_t* datamock_SubscriptionList_create(void) {
    return new datamock_SubscriptionList_t();
}

void datamock_SubscriptionList_destroy(datamock_SubscriptionList_t* list) {
    delete list;
}

int datamock_SubscriptionList_add(
    datamock_SubscriptionList_t* list,
    const char* topic,
    const char* fields,
    const char* options,
    datamock_CorrelationId_t* correlationId)
{
    if (!list || !topic) return DATAMOCK_ERROR_ILLEGAL_ARG;
    try {
        CorrelationId cid;
        if (correlationId && correlationId->valueType == DATAMOCK_CORRELATION_TYPE_INT) {
            cid = CorrelationId(correlationId->value.intValue);
        }
        
        // Build subscription
        Subscription sub(topic, fields ? fields : "", options ? options : "", cid);
        list->list.add(sub);
        return DATAMOCK_OK;
    } catch (...) {
        return DATAMOCK_ERROR_UNKNOWN;
    }
}

size_t datamock_SubscriptionList_size(datamock_SubscriptionList_t* list) {
    if (!list) return 0;
    return list->list.size();
}

/* ============================================================================
 * CorrelationId helpers
 * ============================================================================ */

void datamock_CorrelationId_init(datamock_CorrelationId_t* cid) {
    if (!cid) return;
    cid->size = sizeof(datamock_CorrelationId_t);
    cid->valueType = DATAMOCK_CORRELATION_TYPE_UNSET;
    cid->classId = 0;
    cid->reserved = 0;
    cid->value.intValue = 0;
}

void datamock_CorrelationId_setInt(datamock_CorrelationId_t* cid, uint64_t value) {
    if (!cid) return;
    cid->valueType = DATAMOCK_CORRELATION_TYPE_INT;
    cid->value.intValue = value;
}

void datamock_CorrelationId_setPointer(datamock_CorrelationId_t* cid, void* ptr) {
    if (!cid) return;
    cid->valueType = DATAMOCK_CORRELATION_TYPE_POINTER;
    cid->value.ptrValue = ptr;
}

uint64_t datamock_CorrelationId_asInt(datamock_CorrelationId_t* cid) {
    if (!cid) return 0;
    return cid->value.intValue;
}

void* datamock_CorrelationId_asPointer(datamock_CorrelationId_t* cid) {
    if (!cid) return nullptr;
    return cid->value.ptrValue;
}

int datamock_CorrelationId_type(datamock_CorrelationId_t* cid) {
    if (!cid) return DATAMOCK_CORRELATION_TYPE_UNSET;
    return static_cast<int>(cid->valueType);
}
