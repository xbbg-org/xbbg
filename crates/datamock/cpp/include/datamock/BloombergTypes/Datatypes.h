//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="headers/BloombergTypes/Datatypes.h" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#pragma once

enum blpapi_DataType_t //This is purposely not declared inside of a namespace
{
	BLPAPI_DATATYPE_BOOL           = 1     // Bool
	, BLPAPI_DATATYPE_CHAR           = 2     // Char
	, BLPAPI_DATATYPE_BYTE           = 3     // Unsigned 8 bit value
	, BLPAPI_DATATYPE_INT32          = 4     // 32 bit Integer
	, BLPAPI_DATATYPE_INT64          = 5     // 64 bit Integer
	, BLPAPI_DATATYPE_FLOAT32        = 6     // 32 bit Floating point - IEEE
	, BLPAPI_DATATYPE_FLOAT64        = 7     // 64 bit Floating point - IEEE
	, BLPAPI_DATATYPE_STRING         = 8     // ASCIIZ string
	, BLPAPI_DATATYPE_BYTEARRAY      = 9     // Opaque binary data
	, BLPAPI_DATATYPE_DATE           = 10    // Date
	, BLPAPI_DATATYPE_TIME           = 11    // Timestamp
	, BLPAPI_DATATYPE_DECIMAL        = 12    //
	, BLPAPI_DATATYPE_DATETIME       = 13    // Date and time
	, BLPAPI_DATATYPE_ENUMERATION    = 14    // An opaque enumeration
	, BLPAPI_DATATYPE_SEQUENCE       = 15    // Sequence type
	, BLPAPI_DATATYPE_CHOICE         = 16    // Choice type
	, BLPAPI_DATATYPE_CORRELATION_ID = 17    // Used for some internal messages
};