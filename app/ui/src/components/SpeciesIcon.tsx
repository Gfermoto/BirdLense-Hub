import React from 'react';
import Avatar from '@mui/material/Avatar';
import { BirdIcon } from './icons/BirdIcon';
import { SquirrelIcon } from './icons/SquirrelIcon';
import { isSquirrelLike } from '../util';
import { resolveImageUrl } from '../api/api';

interface SpeciesIconProps {
  speciesName: string;
  imageUrl?: string | null;
  size?: number;
  sx?: object;
}

export const SpeciesIcon: React.FC<SpeciesIconProps> = ({
  speciesName,
  imageUrl,
  size = 48,
  sx = {},
}) => {
  const Icon = isSquirrelLike(speciesName) ? SquirrelIcon : BirdIcon;
  const src = resolveImageUrl(imageUrl);

  return (
    <Avatar
      src={src}
      sx={{
        width: size,
        height: size,
        bgcolor: 'primary.main',
        color: 'primary.contrastText',
        ...sx,
      }}
    >
      <Icon sx={{ fontSize: size * 0.6 }} />
    </Avatar>
  );
};
