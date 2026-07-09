import { describe, expect, it } from 'vitest';
import {
  INFERENCE_LORES_WH_DEFAULT,
  processorDefault,
  processorNumberValue,
  whPairOrDefault,
} from './processorFieldDefaults';

describe('processorFieldDefaults', () => {
  it('uses 704 not 640 for binary_imgsz default', () => {
    expect(processorDefault('binary_imgsz')).toBe(704);
  });

  it('falls back to yaml-aligned default when value missing', () => {
    expect(processorNumberValue(undefined, 'inference_lores_px')).toBe(704);
  });

  it('parses inference lores wh default', () => {
    expect(whPairOrDefault(undefined, INFERENCE_LORES_WH_DEFAULT)).toEqual([
      704, 576,
    ]);
  });
});
