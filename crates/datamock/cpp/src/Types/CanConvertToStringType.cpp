//------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/Types/CanConvertToStringType.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------

#include "Types/CanConvertToStringType.h"

namespace BEmu
{
	CanConvertToStringType::CanConvertToStringType(bool arg, bool surroundWithQuotes)
	{
		this->ResetStringConversion(arg, surroundWithQuotes);
	}

	CanConvertToStringType::CanConvertToStringType(double arg, bool surroundWithQuotes)
	{
		this->ResetStringConversion(arg, surroundWithQuotes);
	}
	
	CanConvertToStringType::CanConvertToStringType(int arg, bool surroundWithQuotes)
	{
		this->ResetStringConversion(arg, surroundWithQuotes);
	}
	
	CanConvertToStringType::CanConvertToStringType(const std::string& arg, bool surroundWithQuotes)
	{
		this->ResetStringConversion(arg, surroundWithQuotes);
	}

	CanConvertToStringType::CanConvertToStringType(const Datetime& arg, bool surroundWithQuotes)
	{
		this->ResetStringConversion(arg, surroundWithQuotes);
	}

	const std::string& CanConvertToStringType::ValueAsString() const
	{
		return this->_valueAsString;
	}

	void CanConvertToStringType::ClearStream()
	{
		this->_ss.str(std::string()); //clears out the stringstream
	}
	
	void CanConvertToStringType::ResetStringConversion(bool arg, bool surroundWithQuotes)
	{
		this->ClearStream();

		if(surroundWithQuotes)
			this->_ss << "\"" << arg << "\"";
		else
			this->_ss << (arg ? "true" : "false");

		this->_valueAsString = this->_ss.str();
	}

	void CanConvertToStringType::ResetStringConversion(int arg, bool surroundWithQuotes)
	{
		this->ClearStream();

		if(surroundWithQuotes)
			this->_ss << "\"" << arg << "\"";
		else
			this->_ss << arg;

		this->_valueAsString = this->_ss.str();
	}

	void CanConvertToStringType::ResetStringConversion(double arg, bool surroundWithQuotes)
	{
		this->ClearStream();

		if(surroundWithQuotes)
			this->_ss << "\"" << arg << "\"";
		else
			this->_ss << arg;

		this->_valueAsString = this->_ss.str();
	}

	void CanConvertToStringType::ResetStringConversion(const std::string& arg, bool surroundWithQuotes)
	{
		this->ClearStream();

		if(surroundWithQuotes)
			this->_ss << "\"" << arg << "\"";
		else
			this->_ss << arg;
		
		this->_valueAsString = this->_ss.str();
	}

	void CanConvertToStringType::ResetStringConversion(const Datetime& arg, bool surroundWithQuotes)
	{
		this->ClearStream();

		if(surroundWithQuotes)
			this->_ss << "\"" << arg << "\"";
		else
			this->_ss << arg;
		
		this->_valueAsString = this->_ss.str();
	}
}