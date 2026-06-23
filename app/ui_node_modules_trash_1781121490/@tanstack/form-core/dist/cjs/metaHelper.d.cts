import { FormApi } from './FormApi.cjs';
import { Validator } from './types.cjs';
import { DeepKeys } from './util-types.cjs';
type ArrayFieldMode = 'insert' | 'remove' | 'swap' | 'move';
export declare function metaHelper<TFormData, TFormValidator extends Validator<TFormData, unknown> | undefined = undefined>(formApi: FormApi<TFormData, TFormValidator>): {
    handleArrayFieldMetaShift: (field: DeepKeys<TFormData>, index: number, mode: ArrayFieldMode, secondIndex?: number) => void;
};
export {};
