//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/ConstantList.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "BloombergTypes/Constant.h"
#include "BloombergTypes/ConstantList.h"
#include "Exceptions/Exception.h"

namespace BEmu
{
	ConstantList::ConstantList(const ConstantList& original) { (void)original; throw BEmu::Exception("not implemented"); }

	void ConstantList::setUserData(void *userData) { (void)userData; throw BEmu::Exception("not implemented"); }
	Name ConstantList::name() const { throw BEmu::Exception("not implemented"); }
	const char * ConstantList::description() const { throw BEmu::Exception("not implemented"); }
	int ConstantList::status() const { throw BEmu::Exception("not implemented"); }
	int ConstantList::numConstants() const { throw BEmu::Exception("not implemented"); }
	int ConstantList::datatype() const { throw BEmu::Exception("not implemented"); }
	Constant ConstantList::getConstant(const Name& name) const { (void)name; throw BEmu::Exception("not implemented"); }
	Constant ConstantList::getConstant(const char *name) const { (void)name; throw BEmu::Exception("not implemented"); }
	Constant ConstantList::getConstantAt(size_t index) const { (void)index; throw BEmu::Exception("not implemented"); }
	void * ConstantList::userData() const { throw BEmu::Exception("not implemented"); }
}