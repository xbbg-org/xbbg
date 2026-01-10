/*
 * datamock C API
 *
 * This header provides a C-compatible API that mirrors the Bloomberg BLPAPI
 * C interface, allowing datamock to be used as a drop-in replacement for
 * testing purposes.
 *
 * Based on BEmu by Jordan Robinson (Ms-PL license).
 */

#ifndef DATAMOCK_C_API_H
#define DATAMOCK_C_API_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Platform-specific export macro */
#ifdef _WIN32
    #ifdef DATAMOCK_BUILDING
        #define DATAMOCK_EXPORT __declspec(dllexport)
    #else
        #define DATAMOCK_EXPORT __declspec(dllimport)
    #endif
#else
    #define DATAMOCK_EXPORT __attribute__((visibility("default")))
#endif

/* ============================================================================
 * Opaque handle types (match blpapi naming)
 * ============================================================================ */

typedef struct datamock_Session_t datamock_Session_t;
typedef struct datamock_SessionOptions_t datamock_SessionOptions_t;
typedef struct datamock_Service_t datamock_Service_t;
typedef struct datamock_Request_t datamock_Request_t;
typedef struct datamock_Event_t datamock_Event_t;
typedef struct datamock_Message_t datamock_Message_t;
typedef struct datamock_Element_t datamock_Element_t;
typedef struct datamock_Name_t datamock_Name_t;
typedef struct datamock_SubscriptionList_t datamock_SubscriptionList_t;
typedef struct datamock_MessageIterator_t datamock_MessageIterator_t;

/* ============================================================================
 * Basic types
 * ============================================================================ */

typedef int datamock_Bool_t;
typedef int32_t datamock_Int32_t;
typedef int64_t datamock_Int64_t;
typedef float datamock_Float32_t;
typedef double datamock_Float64_t;
typedef char datamock_Char_t;

/* ============================================================================
 * Datetime
 * ============================================================================ */

typedef struct datamock_Datetime_t {
    uint8_t parts;       /* Bitmask of which parts are set */
    uint8_t hours;
    uint8_t minutes;
    uint8_t seconds;
    uint16_t milliSeconds;
    uint8_t month;
    uint8_t day;
    uint16_t year;
    int16_t offset;      /* Timezone offset in minutes */
} datamock_Datetime_t;

/* Datetime parts bitmask */
#define DATAMOCK_DATETIME_YEAR_PART         0x01
#define DATAMOCK_DATETIME_MONTH_PART        0x02
#define DATAMOCK_DATETIME_DAY_PART          0x04
#define DATAMOCK_DATETIME_OFFSET_PART       0x08
#define DATAMOCK_DATETIME_HOURS_PART        0x10
#define DATAMOCK_DATETIME_MINUTES_PART      0x20
#define DATAMOCK_DATETIME_SECONDS_PART      0x40
#define DATAMOCK_DATETIME_MILLISECONDS_PART 0x80

#define DATAMOCK_DATETIME_DATE_PART \
    (DATAMOCK_DATETIME_YEAR_PART | DATAMOCK_DATETIME_MONTH_PART | DATAMOCK_DATETIME_DAY_PART)

#define DATAMOCK_DATETIME_TIME_PART \
    (DATAMOCK_DATETIME_HOURS_PART | DATAMOCK_DATETIME_MINUTES_PART | \
     DATAMOCK_DATETIME_SECONDS_PART | DATAMOCK_DATETIME_MILLISECONDS_PART)

/* ============================================================================
 * CorrelationId
 * ============================================================================ */

/* ManagedPtr for pointer-type correlation IDs */
typedef void* datamock_ManagedPtr_t_data_;
typedef void (*datamock_ManagedPtr_ManagerFunction_t)(void*, void*);

typedef struct datamock_ManagedPtr_t_ {
    void* pointer;
    datamock_ManagedPtr_t_data_ userData[4];
    datamock_ManagedPtr_ManagerFunction_t manager;
} datamock_ManagedPtr_t;

/* CorrelationId with bitfield layout matching Bloomberg BLPAPI */
typedef struct datamock_CorrelationId_t {
    unsigned int size : 8;
    unsigned int valueType : 4;
    unsigned int classId : 16;
    unsigned int reserved : 4;
    union {
        uint64_t intValue;
        datamock_ManagedPtr_t ptrValue;
    } value;
} datamock_CorrelationId_t;

#define DATAMOCK_CORRELATION_TYPE_UNSET   0
#define DATAMOCK_CORRELATION_TYPE_INT     1
#define DATAMOCK_CORRELATION_TYPE_POINTER 2
#define DATAMOCK_CORRELATION_TYPE_AUTOGEN 3

/* ============================================================================
 * Data types
 * ============================================================================ */

typedef enum datamock_DataType_t {
    DATAMOCK_DATATYPE_BOOL = 1,
    DATAMOCK_DATATYPE_CHAR = 2,
    DATAMOCK_DATATYPE_BYTE = 3,
    DATAMOCK_DATATYPE_INT32 = 4,
    DATAMOCK_DATATYPE_INT64 = 5,
    DATAMOCK_DATATYPE_FLOAT32 = 6,
    DATAMOCK_DATATYPE_FLOAT64 = 7,
    DATAMOCK_DATATYPE_STRING = 8,
    DATAMOCK_DATATYPE_BYTEARRAY = 9,
    DATAMOCK_DATATYPE_DATE = 10,
    DATAMOCK_DATATYPE_TIME = 11,
    DATAMOCK_DATATYPE_DECIMAL = 12,
    DATAMOCK_DATATYPE_DATETIME = 13,
    DATAMOCK_DATATYPE_ENUMERATION = 14,
    DATAMOCK_DATATYPE_SEQUENCE = 15,
    DATAMOCK_DATATYPE_CHOICE = 16,
    DATAMOCK_DATATYPE_CORRELATION_ID = 17
} datamock_DataType_t;

/* ============================================================================
 * Event types
 * ============================================================================ */

typedef enum datamock_EventType_t {
    DATAMOCK_EVENTTYPE_ADMIN = 1,
    DATAMOCK_EVENTTYPE_SESSION_STATUS = 2,
    DATAMOCK_EVENTTYPE_SUBSCRIPTION_STATUS = 3,
    DATAMOCK_EVENTTYPE_REQUEST_STATUS = 4,
    DATAMOCK_EVENTTYPE_RESPONSE = 5,
    DATAMOCK_EVENTTYPE_PARTIAL_RESPONSE = 6,
    DATAMOCK_EVENTTYPE_SUBSCRIPTION_DATA = 8,
    DATAMOCK_EVENTTYPE_SERVICE_STATUS = 9,
    DATAMOCK_EVENTTYPE_TIMEOUT = 10,
    DATAMOCK_EVENTTYPE_AUTHORIZATION_STATUS = 11,
    DATAMOCK_EVENTTYPE_RESOLUTION_STATUS = 12,
    DATAMOCK_EVENTTYPE_TOPIC_STATUS = 13,
    DATAMOCK_EVENTTYPE_TOKEN_STATUS = 14,
    DATAMOCK_EVENTTYPE_REQUEST = 15
} datamock_EventType_t;

/* ============================================================================
 * Error codes
 * ============================================================================ */

#define DATAMOCK_OK                          0
#define DATAMOCK_ERROR_UNKNOWN              -1
#define DATAMOCK_ERROR_ILLEGAL_ARG          -2
#define DATAMOCK_ERROR_NOT_FOUND            -3
#define DATAMOCK_ERROR_INVALID_STATE        -4
#define DATAMOCK_ERROR_TIMED_OUT            -5

/* ============================================================================
 * SessionOptions
 * ============================================================================ */

DATAMOCK_EXPORT datamock_SessionOptions_t* datamock_SessionOptions_create(void);
DATAMOCK_EXPORT void datamock_SessionOptions_destroy(datamock_SessionOptions_t* options);
DATAMOCK_EXPORT int datamock_SessionOptions_setServerHost(datamock_SessionOptions_t* options, const char* host);
DATAMOCK_EXPORT int datamock_SessionOptions_setServerPort(datamock_SessionOptions_t* options, uint16_t port);
DATAMOCK_EXPORT const char* datamock_SessionOptions_serverHost(datamock_SessionOptions_t* options);
DATAMOCK_EXPORT uint16_t datamock_SessionOptions_serverPort(datamock_SessionOptions_t* options);

/* ============================================================================
 * Session
 * ============================================================================ */

typedef void (*datamock_EventHandler_t)(datamock_Event_t* event, datamock_Session_t* session, void* userData);

DATAMOCK_EXPORT datamock_Session_t* datamock_Session_create(
    datamock_SessionOptions_t* options,
    datamock_EventHandler_t handler,
    void* userData);
DATAMOCK_EXPORT void datamock_Session_destroy(datamock_Session_t* session);
DATAMOCK_EXPORT int datamock_Session_start(datamock_Session_t* session);
DATAMOCK_EXPORT int datamock_Session_startAsync(datamock_Session_t* session);
DATAMOCK_EXPORT int datamock_Session_stop(datamock_Session_t* session);
DATAMOCK_EXPORT int datamock_Session_stopAsync(datamock_Session_t* session);
DATAMOCK_EXPORT int datamock_Session_openService(datamock_Session_t* session, const char* uri);
DATAMOCK_EXPORT int datamock_Session_openServiceAsync(
    datamock_Session_t* session,
    const char* uri,
    datamock_CorrelationId_t* correlationId);
DATAMOCK_EXPORT int datamock_Session_getService(
    datamock_Session_t* session,
    datamock_Service_t** service,
    const char* uri);
DATAMOCK_EXPORT int datamock_Session_sendRequest(
    datamock_Session_t* session,
    datamock_Request_t* request,
    datamock_CorrelationId_t* correlationId,
    const char* requestLabel);
DATAMOCK_EXPORT int datamock_Session_nextEvent(
    datamock_Session_t* session,
    datamock_Event_t** event,
    uint32_t timeoutMs);
DATAMOCK_EXPORT int datamock_Session_tryNextEvent(
    datamock_Session_t* session,
    datamock_Event_t** event);
DATAMOCK_EXPORT int datamock_Session_subscribe(
    datamock_Session_t* session,
    datamock_SubscriptionList_t* subscriptions);
DATAMOCK_EXPORT int datamock_Session_unsubscribe(
    datamock_Session_t* session,
    datamock_SubscriptionList_t* subscriptions);
DATAMOCK_EXPORT int datamock_Session_cancel(
    datamock_Session_t* session,
    datamock_CorrelationId_t* correlationIds,
    size_t numCorrelationIds);

/* ============================================================================
 * Service
 * ============================================================================ */

DATAMOCK_EXPORT int datamock_Service_createRequest(
    datamock_Service_t* service,
    datamock_Request_t** request,
    const char* operationName);
DATAMOCK_EXPORT const char* datamock_Service_name(datamock_Service_t* service);

/* ============================================================================
 * Request
 * ============================================================================ */

DATAMOCK_EXPORT void datamock_Request_destroy(datamock_Request_t* request);
DATAMOCK_EXPORT int datamock_Request_getElement(
    datamock_Request_t* request,
    datamock_Element_t** element);
DATAMOCK_EXPORT int datamock_Request_append(
    datamock_Request_t* request,
    const char* name,
    const char* value);
DATAMOCK_EXPORT int datamock_Request_set(
    datamock_Request_t* request,
    const char* name,
    const char* value);
DATAMOCK_EXPORT int datamock_Request_setInt32(
    datamock_Request_t* request,
    const char* name,
    int32_t value);
DATAMOCK_EXPORT int datamock_Request_setDatetime(
    datamock_Request_t* request,
    const char* name,
    const datamock_Datetime_t* value);

/* ============================================================================
 * Event
 * ============================================================================ */

DATAMOCK_EXPORT void datamock_Event_release(datamock_Event_t* event);
DATAMOCK_EXPORT datamock_EventType_t datamock_Event_eventType(datamock_Event_t* event);
DATAMOCK_EXPORT int datamock_MessageIterator_create(
    datamock_MessageIterator_t** iterator,
    datamock_Event_t* event);
DATAMOCK_EXPORT void datamock_MessageIterator_destroy(datamock_MessageIterator_t* iterator);
DATAMOCK_EXPORT int datamock_MessageIterator_next(
    datamock_MessageIterator_t* iterator,
    datamock_Message_t** message);

/* ============================================================================
 * Message
 * ============================================================================ */

DATAMOCK_EXPORT int datamock_Message_elements(
    datamock_Message_t* message,
    datamock_Element_t** element);
DATAMOCK_EXPORT int datamock_Message_correlationId(
    datamock_Message_t* message,
    datamock_CorrelationId_t* correlationId,
    size_t index);
DATAMOCK_EXPORT size_t datamock_Message_numCorrelationIds(datamock_Message_t* message);
DATAMOCK_EXPORT const char* datamock_Message_typeString(datamock_Message_t* message);
DATAMOCK_EXPORT const char* datamock_Message_topicName(datamock_Message_t* message);

/* ============================================================================
 * Element
 * ============================================================================ */

DATAMOCK_EXPORT datamock_DataType_t datamock_Element_datatype(datamock_Element_t* element);
DATAMOCK_EXPORT int datamock_Element_isArray(datamock_Element_t* element);
DATAMOCK_EXPORT int datamock_Element_isComplexType(datamock_Element_t* element);
DATAMOCK_EXPORT int datamock_Element_isNull(datamock_Element_t* element);
DATAMOCK_EXPORT size_t datamock_Element_numValues(datamock_Element_t* element);
DATAMOCK_EXPORT size_t datamock_Element_numElements(datamock_Element_t* element);
DATAMOCK_EXPORT int datamock_Element_nameString(
    datamock_Element_t* element,
    const char** name);
DATAMOCK_EXPORT int datamock_Element_hasElement(
    datamock_Element_t* element,
    const char* name,
    datamock_Bool_t excludeNullElements);
DATAMOCK_EXPORT int datamock_Element_getElement(
    datamock_Element_t* element,
    datamock_Element_t** result,
    const char* name);
DATAMOCK_EXPORT int datamock_Element_getElementAt(
    datamock_Element_t* element,
    datamock_Element_t** result,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsBool(
    datamock_Element_t* element,
    datamock_Bool_t* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsInt32(
    datamock_Element_t* element,
    datamock_Int32_t* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsInt64(
    datamock_Element_t* element,
    datamock_Int64_t* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsFloat32(
    datamock_Element_t* element,
    datamock_Float32_t* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsFloat64(
    datamock_Element_t* element,
    datamock_Float64_t* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsString(
    datamock_Element_t* element,
    const char** value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsDatetime(
    datamock_Element_t* element,
    datamock_Datetime_t* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_getValueAsElement(
    datamock_Element_t* element,
    datamock_Element_t** value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_setValueString(
    datamock_Element_t* element,
    const char* value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_setValueInt32(
    datamock_Element_t* element,
    datamock_Int32_t value,
    size_t index);
DATAMOCK_EXPORT int datamock_Element_appendValue(
    datamock_Element_t* element,
    const char* value);

/* JSON serialization (matches blpapi_Element_toJson signature) */
typedef int (*datamock_StreamWriter_t)(const char* data, int length, void* stream);

DATAMOCK_EXPORT int datamock_Element_toJson(
    const datamock_Element_t* element,
    datamock_StreamWriter_t writer,
    void* stream);

/* ============================================================================
 * Name
 * ============================================================================ */

DATAMOCK_EXPORT datamock_Name_t* datamock_Name_create(const char* nameString);
DATAMOCK_EXPORT void datamock_Name_destroy(datamock_Name_t* name);
DATAMOCK_EXPORT const char* datamock_Name_string(datamock_Name_t* name);

/* ============================================================================
 * SubscriptionList
 * ============================================================================ */

DATAMOCK_EXPORT datamock_SubscriptionList_t* datamock_SubscriptionList_create(void);
DATAMOCK_EXPORT void datamock_SubscriptionList_destroy(datamock_SubscriptionList_t* list);
DATAMOCK_EXPORT int datamock_SubscriptionList_add(
    datamock_SubscriptionList_t* list,
    const char* topic,
    const char* fields,
    const char* options,
    datamock_CorrelationId_t* correlationId);
DATAMOCK_EXPORT size_t datamock_SubscriptionList_size(datamock_SubscriptionList_t* list);

/* ============================================================================
 * CorrelationId helpers
 * ============================================================================ */

DATAMOCK_EXPORT void datamock_CorrelationId_init(datamock_CorrelationId_t* cid);
DATAMOCK_EXPORT void datamock_CorrelationId_setInt(datamock_CorrelationId_t* cid, uint64_t value);
DATAMOCK_EXPORT void datamock_CorrelationId_setPointer(datamock_CorrelationId_t* cid, void* ptr);
DATAMOCK_EXPORT uint64_t datamock_CorrelationId_asInt(datamock_CorrelationId_t* cid);
DATAMOCK_EXPORT void* datamock_CorrelationId_asPointer(datamock_CorrelationId_t* cid);
DATAMOCK_EXPORT int datamock_CorrelationId_type(datamock_CorrelationId_t* cid);

/* Extended helpers matching blpapiext_cid_* signatures */
DATAMOCK_EXPORT int datamockext_cid_from_ptr(datamock_CorrelationId_t* out, const void* p);
DATAMOCK_EXPORT int datamockext_cid_get_ptr(const datamock_CorrelationId_t* cid, void** out);

#ifdef __cplusplus
}
#endif

#endif /* DATAMOCK_C_API_H */
