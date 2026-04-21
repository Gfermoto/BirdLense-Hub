import SvgIcon, { SvgIconProps } from '@mui/material/SvgIcon';

/** Иконка грызуна (Rodent) — для Rodent и совместимых имён из внешних источников */
export const RodentIcon = (props: SvgIconProps) => (
  <SvgIcon {...props} viewBox="0 0 24 24">
    <ellipse cx="12" cy="14" rx="5" ry="6" fill="currentColor" />
    <circle cx="12" cy="8" r="4" fill="currentColor" />
    <circle cx="9" cy="5" r="1.5" fill="currentColor" />
    <circle cx="15" cy="5" r="1.5" fill="currentColor" />
    <ellipse cx="18" cy="12" rx="3" ry="4" fill="currentColor" opacity="0.9" />
  </SvgIcon>
);

export default RodentIcon;
