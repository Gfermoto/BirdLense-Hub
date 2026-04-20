import { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  const [showPassword, setShowPassword] = useState(false);
  const isMasked = value === MASK_PLACEHOLDER;

  return (
    <TextField
      fullWidth={fullWidth}
      variant="outlined"
      type={showPassword && !isMasked ? 'text' : 'password'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      label={label}
      placeholder={placeholder}
      helperText={helperText}
      error={error}
      disabled={disabled}
      autoFocus={autoFocus}
      /* В диалогах и плотных формах «всплывающая» метка обрезается сверху — держим в вырезе рамки. */
      InputLabelProps={{ shrink: true }}
      InputProps={{
        endAdornment: !isMasked ? (
          <InputAdornment position="end">
            <IconButton
              aria-label={
                showPassword
                  ? t('common.hidePassword')
                  : t('common.showPassword')
              }
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
