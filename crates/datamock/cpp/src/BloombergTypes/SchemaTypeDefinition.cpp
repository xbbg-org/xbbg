//------------------------------------------------------------------------------------------------
// <copyright project="BEmu_cpp" file="src/BloombergTypes/SchemaTypeDefinition.cpp" company="Jordan Robinson">
//     Copyright (c) 2013 Jordan Robinson. All rights reserved.
//
//     The use of this software is governed by the Microsoft Public License
//     which is included with this distribution.
// </copyright>
//------------------------------------------------------------------------------------------------

#include "Exceptions/Exception.h"
#include "BloombergTypes/SchemaTypeDefinition.h"
#include <ostream>

namespace BEmu
{
	SchemaTypeDefinition::~SchemaTypeDefinition() { throw BEmu::Exception("not implemented"); }

	void SchemaTypeDefinition::setUserData(void *userData) { (void)userData; throw BEmu::Exception("not implemented"); }
	int SchemaTypeDefinition::datatype() const { throw BEmu::Exception("not implemented"); }
	Name SchemaTypeDefinition::name() const { throw BEmu::Exception("not implemented"); }
	const char * SchemaTypeDefinition::description() const { throw BEmu::Exception("not implemented"); }
	int SchemaTypeDefinition::status() const { throw BEmu::Exception("not implemented"); }
	size_t SchemaTypeDefinition::numElementDefinitions() const { throw BEmu::Exception("not implemented"); }
	bool SchemaTypeDefinition::isComplexType() const { throw BEmu::Exception("not implemented"); }
	bool SchemaTypeDefinition::isSimpleType() const { throw BEmu::Exception("not implemented"); }
	bool SchemaTypeDefinition::isEnumerationType() const { throw BEmu::Exception("not implemented"); }
	bool SchemaTypeDefinition::hasElementDefinition(const Name& name) const { (void)name; throw BEmu::Exception("not implemented"); }
	bool SchemaTypeDefinition::hasElementDefinition(const char *name) const { (void)name; throw BEmu::Exception("not implemented"); }
	SchemaElementDefinition SchemaTypeDefinition::getElementDefinition(const Name& name) const { (void)name; throw BEmu::Exception("not implemented"); }
	SchemaElementDefinition SchemaTypeDefinition::getElementDefinition(const char *nameString) const { (void)nameString; throw BEmu::Exception("not implemented"); }
	SchemaElementDefinition SchemaTypeDefinition::getElementDefinition(size_t index) const { (void)index; throw BEmu::Exception("not implemented"); }
	const ConstantList SchemaTypeDefinition::enumeration() const { throw BEmu::Exception("not implemented"); }
	void * SchemaTypeDefinition::userData() const { throw BEmu::Exception("not implemented"); }
	
	std::ostream& SchemaTypeDefinition::print(std::ostream& stream, int level, int spacesPerLevel) const { (void)stream; (void)level; (void)spacesPerLevel; throw BEmu::Exception("not implemented"); }

	std::ostream& operator<<(std::ostream& stream, const SchemaTypeDefinition& typeDef) { (void)stream; (void)typeDef; throw BEmu::Exception("not implemented"); }
}