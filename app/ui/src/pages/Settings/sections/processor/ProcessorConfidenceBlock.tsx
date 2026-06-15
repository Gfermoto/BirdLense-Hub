import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';
type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};
... (175 more lines)
[lean-ctx: 1459→98 tok, -93%]
