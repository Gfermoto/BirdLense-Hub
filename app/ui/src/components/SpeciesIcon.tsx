import React, { useEffect, useState } from 'react';
import Avatar from '@mui/material/Avatar';
import { BirdIcon } from './icons/BirdIcon';
import { RodentIcon } from './icons/RodentIcon';
import { isRodentLike } from '../util';
import { resolveImageUrl } from '../api/birdFoodFeed';

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
  const Icon = isRodentLike(speciesName) ? RodentIcon : BirdIcon;
  const [imageFailed, setImageFailed] = useState(false);
  const src = imageFailed ? undefined : resolveImageUrl(imageUrl);

  useEffect(() => {
    setImageFailed(false);
  }, [imageUrl, speciesName]);

  return (
    <Avatar
      src={src}
      imgProps={
        src
          ? {
              alt: speciesName,
              onError: () => setImageFailed(true),
            }
          : undefined
      }
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
