import {
  Bool,
  DateDay,
  Field,
  Float64,
  Int32,
  Int64,
  Null,
  RecordBatch,
  Schema,
  Struct,
  Table,
  TimeMicrosecond,
  TimestampMicrosecond,
  Utf8,
  makeData,
  type Data,
  type DataType,
} from 'apache-arrow';

import type { NativeArrowColumn, NativeArrowZeroCopyBatch } from './napi';

const NATIVE_ARROW_BUFFERS = Symbol('@xbbg/nativeArrowBuffers');

type TypedArrayConstructor<T extends ArrayBufferView> = new (
  buffer: ArrayBufferLike,
  byteOffset: number,
  length: number,
) => T;

export function tableFromNativeArrowBatch(batch: NativeArrowZeroCopyBatch): Table {
  const retainedBuffers: Buffer[] = [];
  const fields = batch.columns.map((column) => {
    const type = arrowType(column);
    return new Field(column.name, type, column.nullable);
  });
  const children = batch.columns.map((column) => dataFromColumn(column, retainedBuffers));

  const schema = new Schema(fields);
  const structData = makeData({
    type: new Struct(fields),
    length: batch.numRows,
    children,
  });
  const table = new Table(schema, new RecordBatch(schema, structData));

  // Keep the original Node Buffer views alive. Numeric Arrow vectors retain typed
  // views over the same backing ArrayBuffers, but keeping these Buffer objects on
  // the Table makes the NAPI external-buffer lifetime explicit.
  Object.defineProperty(table, NATIVE_ARROW_BUFFERS, {
    value: retainedBuffers,
    enumerable: false,
  });

  return table;
}

function dataFromColumn(
  column: NativeArrowColumn,
  retainedBuffers: Buffer[],
): Data {
  const nullBitmap = optionalUint8View(column.nullBitmap, retainedBuffers);
  switch (column.type) {
    case 'bool':
      return makeData({
        type: new Bool(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredUint8View(column, retainedBuffers, Math.ceil(column.length / 8)),
      });
    case 'date32':
      return makeData({
        type: new DateDay(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredTypedView(column, Int32Array, retainedBuffers),
      });
    case 'float64':
      return makeData({
        type: new Float64(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredTypedView(column, Float64Array, retainedBuffers),
      });
    case 'int32':
      return makeData({
        type: new Int32(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredTypedView(column, Int32Array, retainedBuffers),
      });
    case 'int64':
      return makeData({
        type: new Int64(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredTypedView(column, BigInt64Array, retainedBuffers),
      });
    case 'null':
      return makeData({
        type: new Null(),
        length: column.length,
      });
    case 'time64_us':
      return makeData({
        type: new TimeMicrosecond(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredTypedView(column, BigInt64Array, retainedBuffers),
      });
    case 'timestamp_us':
      return makeData({
        type: new TimestampMicrosecond(column.timezone),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        data: requiredTypedView(column, BigInt64Array, retainedBuffers),
      });
    case 'utf8':
      return makeData({
        type: new Utf8(),
        length: column.length,
        nullCount: column.nullCount,
        nullBitmap,
        valueOffsets: requiredOffsets(column, retainedBuffers),
        data: requiredUint8View(column, retainedBuffers),
      });
  }
}

function arrowType(column: NativeArrowColumn): DataType {
  switch (column.type) {
    case 'bool':
      return new Bool();
    case 'date32':
      return new DateDay();
    case 'float64':
      return new Float64();
    case 'int32':
      return new Int32();
    case 'int64':
      return new Int64();
    case 'null':
      return new Null();
    case 'time64_us':
      return new TimeMicrosecond();
    case 'timestamp_us':
      return new TimestampMicrosecond(column.timezone);
    case 'utf8':
      return new Utf8();
  }
}

function requiredTypedView<T extends ArrayBufferView>(
  column: NativeArrowColumn,
  ctor: TypedArrayConstructor<T>,
  retainedBuffers: Buffer[],
): T {
  const buffer = requireBuffer(column, 'data');
  retainedBuffers.push(buffer);
  return new ctor(buffer.buffer, buffer.byteOffset, column.length);
}

function requiredOffsets(
  column: NativeArrowColumn,
  retainedBuffers: Buffer[],
): Int32Array {
  const buffer = requireBuffer(column, 'offsets');
  retainedBuffers.push(buffer);
  return new Int32Array(buffer.buffer, buffer.byteOffset, column.length + 1);
}

function requiredUint8View(
  column: NativeArrowColumn,
  retainedBuffers: Buffer[],
  byteLength?: number,
): Uint8Array {
  const buffer = requireBuffer(column, 'data');
  retainedBuffers.push(buffer);
  return new Uint8Array(buffer.buffer, buffer.byteOffset, byteLength ?? buffer.byteLength);
}

function optionalUint8View(
  buffer: Buffer | undefined,
  retainedBuffers: Buffer[],
): Uint8Array | undefined {
  if (buffer === undefined) {
    return undefined;
  }
  retainedBuffers.push(buffer);
  return new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength);
}

function requireBuffer(
  column: NativeArrowColumn,
  property: 'data' | 'offsets',
): Buffer {
  const buffer = column[property];
  if (buffer === undefined) {
    throw new Error(`native Arrow column ${column.name} is missing ${property} buffer`);
  }
  return buffer;
}
