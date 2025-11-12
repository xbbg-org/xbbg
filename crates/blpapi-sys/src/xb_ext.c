#include <stdint.h>
#include <string.h>
#include "blpapi_correlationid.h"

#if defined(__cplusplus)
extern "C" {
#endif

int blpapiext_cid_autogen(blpapi_CorrelationId_t* out) {
    if (!out) return -1;
    // Match C++ default-constructed CorrelationId: fully zeroed (UNSET)
    memset(out, 0, sizeof(*out));
    return 0;
}

int blpapiext_cid_from_u64(blpapi_CorrelationId_t* out, uint64_t value) {
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    out->size = (unsigned int)sizeof(*out);
    out->valueType = BLPAPI_CORRELATION_TYPE_INT;
    out->classId = 0;
    out->value.intValue = (blpapi_UInt64_t)value;
    return 0;
}

int blpapiext_cid_from_ptr(blpapi_CorrelationId_t* out, const void* p) {
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    out->size = (unsigned int)sizeof(*out);
    out->valueType = BLPAPI_CORRELATION_TYPE_POINTER;
    out->classId = 0;
    out->value.ptrValue.pointer = (void*)p;
    out->value.ptrValue.manager = 0;
    return 0;
}

int blpapiext_cid_is_int(const blpapi_CorrelationId_t* cid) {
    if (!cid) return 0;
    return cid->valueType == BLPAPI_CORRELATION_TYPE_INT;
}

int blpapiext_cid_is_ptr(const blpapi_CorrelationId_t* cid) {
    if (!cid) return 0;
    return cid->valueType == BLPAPI_CORRELATION_TYPE_POINTER;
}

int blpapiext_cid_get_u64(const blpapi_CorrelationId_t* cid, uint64_t* out) {
    if (!cid || !out) return -1;
    if (cid->valueType != BLPAPI_CORRELATION_TYPE_INT) return -2;
    *out = (uint64_t)cid->value.intValue;
    return 0;
}

int blpapiext_cid_get_ptr(const blpapi_CorrelationId_t* cid, const void** out) {
    if (!cid || !out) return -1;
    if (cid->valueType != BLPAPI_CORRELATION_TYPE_POINTER) return -2;
    *out = (const void*)cid->value.ptrValue.pointer;
    return 0;
}

#if defined(__cplusplus)
}
#endif

