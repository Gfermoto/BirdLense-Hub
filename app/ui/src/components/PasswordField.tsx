import { useState } from 'react';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';

type PasswordFieldProps = {
  value: string;
  onChange: (v: string) => void;
  label: string;
  placeholder?: string;
  helperText?: string;
  error?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  autoFocus?: boolean;
};

const MASK_PLACEHOLDER = '***';

export function PasswordField({
  value,
  onChange,
  label,
  placeholder,
  helperText,
  error,
  disabled,
  fullWidth = true,
  autoFocus,
}: PasswordFieldProps) {
  const [showPassword, setShowPassword] = useState(false);
  const isMasked = value === MASK_PLACEHOLDER;

  return (
    <TextField
      fullWidth={fullWidth}
      type={showPassword && !isMasked ? 'text' : 'password'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      label={label}
      placeholder={placeholder}
      helperText={helperText}
      error={error}
      disabled={disabled}
      autoFocus={autoFocus}
      InputProps={{
        endAdornment: !isMasked ? (
          <InputAdornment position="end">
            <IconButton
              aria-label={showPassword ? 'hide password' : 'show password'}
              onClick={() => setShowPassword((s) => !s)}
              edge="end"
              size="small"
            >
              {showPassword ? <VisibilityOff /> : <Visibility />}
            </IconButton>
          </InputAdornment>
        ) : undefined,
      }}
    />
  );
}
