import TextField from '@mui/material/TextField';
import type { TextFieldProps } from '@mui/material/TextField';
import {
  parseProcessorNumberInput,
  processorNumberValue,
  type ProcessorDefaultKey,
} from './processorFieldDefaults';

type Props = Omit<TextFieldProps, 'value' | 'onChange' | 'type'> & {
  value: number | null | undefined;
  defaultKey: ProcessorDefaultKey;
  onValueChange: (next: number) => void;
  inputProps?: TextFieldProps['inputProps'];
};

/** Numeric processor field with YAML-aligned default (no hardcoded 640). */
export function ProcessorNumberField({
  value,
  defaultKey,
  onValueChange,
  inputProps,
  ...rest
}: Props) {
  return (
    <TextField
      {...rest}
      fullWidth
      type="number"
      inputProps={inputProps}
      value={processorNumberValue(value, defaultKey)}
      onChange={(e) =>
        onValueChange(parseProcessorNumberInput(e.target.value, defaultKey))
      }
    />
  );
}
