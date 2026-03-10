import SvgIcon, { SvgIconProps } from '@mui/material/SvgIcon';

/** Squirrel icon — used for squirrel/chipmunk/mouse species */
export const SquirrelIcon = (props: SvgIconProps) => (
  <SvgIcon {...props} viewBox="0 0 24 24">
    {/* Body */}
    <ellipse cx="12" cy="14" rx="5" ry="6" fill="currentColor" />
    {/* Head */}
    <circle cx="12" cy="8" r="4" fill="currentColor" />
    {/* Ears */}
    <circle cx="9" cy="5" r="1.5" fill="currentColor" />
    <circle cx="15" cy="5" r="1.5" fill="currentColor" />
    {/* Tail (fluffy) */}
    <ellipse cx="18" cy="12" rx="3" ry="4" fill="currentColor" opacity="0.9" />
  </SvgIcon>
);

export default SquirrelIcon;
