//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/Constant.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Constant.h"
#include "Exceptions/Exception.h"

namespace BEmu
{
	Constant::Constant(const Constant& original) { (void)original; throw BEmu::Exception("not implemented"); }

	void setUserData(void *userData);

	Name Constant::name() const { throw BEmu::Exception("not implemented"); }
	const char * Constant::description() const { throw BEmu::Exception("not implemented"); }
	int Constant::status() const { throw BEmu::Exception("not implemented"); }
	int Constant::datatype() const { throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(char *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(int *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(long *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(float *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(double *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(Datetime *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	int Constant::getValueAs(std::string *buffer) const { (void)buffer; throw BEmu::Exception("not implemented"); }
	char Constant::getValueAsChar() const { throw BEmu::Exception("not implemented"); }
	int Constant::getValueAsInt32() const { throw BEmu::Exception("not implemented"); }
	long Constant::getValueAsInt64() const { throw BEmu::Exception("not implemented"); }
	float Constant::getValueAsFloat32() const { throw BEmu::Exception("not implemented"); }
	double Constant::getValueAsFloat64() const { throw BEmu::Exception("not implemented"); }
	Datetime Constant::getValueAsDatetime() const { throw BEmu::Exception("not implemented"); }
	std::string Constant::getValueAsString() const { throw BEmu::Exception("not implemented"); }
	void * Constant::userData() const { throw BEmu::Exception("not implemented"); }
}