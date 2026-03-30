import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import Info from '@mui/icons-material/Info';
import Tooltip from '@mui/material/Tooltip';
import { resolveImageUrl, fetchBirdFood, toggleBirdFood } from '../../api/api';
import { BirdFood } from '../../types';
import { PageHelp } from '../../components/PageHelp';
import { foodHelpConfig } from '../../page-help-config';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';

const isApplePiecesFood = (food: BirdFood) => {
  const name = (food.name || '').trim().toLowerCase();
  const imageUrl = (food.image_url || '').trim().toLowerCase();
  return name === 'apple pieces' || imageUrl.endsWith('apple-pieces.svg');
};

const ApplePiecesThumbnail = () => (
  <Box
    component="svg"
    viewBox="0 0 120 120"
    aria-label="Apple pieces"
    sx={{
      width: 64,
      height: 64,
      borderRadius: 1.5,
      border: '1px solid',
      borderColor: 'divider',
      bgcolor: 'background.paper',
      p: 0.5,
      flexShrink: 0,
    }}
  >
    <defs>
      <linearGradient id="apple-skin" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#ff6b4a" />
        <stop offset="55%" stopColor="#e62828" />
        <stop offset="100%" stopColor="#a31414" />
      </linearGradient>
      <linearGradient id="apple-flesh" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="#fff8e8" />
        <stop offset="100%" stopColor="#f5e0b8" />
      </linearGradient>
    </defs>
    <path fill="#3d6b2e" d="M58 8c4-6 12-8 18-6-2 6-8 10-14 10-2 0-3-2-4-4z" />
    <ellipse cx="42" cy="38" rx="28" ry="32" fill="url(#apple-skin)" transform="rotate(-18 42 38)" />
    <ellipse cx="78" cy="44" rx="26" ry="30" fill="url(#apple-skin)" transform="rotate(14 78 44)" />
    <path fill="url(#apple-flesh)" d="M34 52c10 14 22 18 36 10 8-4 12-12 10-22-6 8-18 14-30 12-8-1-14-4-16 0z" />
    <path
      fill="none"
      stroke="#8b0000"
      strokeWidth="2"
      strokeLinecap="round"
      opacity="0.35"
      d="M48 30c6 4 10 12 8 20M72 36c-4 6-4 14 0 20"
    />
    <ellipse cx="62" cy="78" rx="22" ry="10" fill="url(#apple-flesh)" stroke="#d4a574" strokeWidth="1.5" />
    <ellipse cx="62" cy="78" rx="3" ry="2" fill="#c4a35a" opacity="0.7" />
  </Box>
);

export const FoodManagement = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { isAdmin } = useProtectedArea();
  const [brokenImages, setBrokenImages] = useState<Record<number, boolean>>({});
  const { data: foodData, isLoading } = useQuery({
    queryKey: ['birdFood'],
    queryFn: fetchBirdFood,
  });

  const toggleMutation = useMutation({
    mutationFn: toggleBirdFood,
    onMutate: async (foodId) => {
      await queryClient.cancelQueries({ queryKey: ['birdFood'] });
      const previousFoods = queryClient.getQueryData(['birdFood']);

      queryClient.setQueryData(['birdFood'], (old: BirdFood[]) =>
        old.map((food) =>
          food.id === foodId ? { ...food, active: !food.active } : food,
        ),
      );

      return { previousFoods };
    },
    onError: (err, variables, context) => {
      queryClient.setQueryData(['birdFood'], context?.previousFoods);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['birdFood'] });
    },
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box mb={4}>
      <PageHelp {...foodHelpConfig} />
      {!isAdmin && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t('food.loginRequired')}
        </Alert>
      )}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t('food.food')}</TableCell>
              <TableCell>{t('food.description')}</TableCell>
              <TableCell align="center">{t('food.active')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(foodData as BirdFood[]).map((food) => (
              <TableRow key={food.id} hover>
                <TableCell sx={{ width: '250px' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    {isApplePiecesFood(food) ? (
                      <ApplePiecesThumbnail />
                    ) : food.image_url && !brokenImages[food.id] ? (
                      <Box
                        component="img"
                        src={resolveImageUrl(food.image_url)}
                        alt={food.name}
                        onError={() =>
                          setBrokenImages((prev) => ({ ...prev, [food.id]: true }))
                        }
                        sx={{
                          width: 64,
                          height: 64,
                          objectFit: 'contain',
                          borderRadius: 1.5,
                          border: '1px solid',
                          borderColor: 'divider',
                          bgcolor: 'background.paper',
                          p: 0.5,
                          flexShrink: 0,
                        }}
                      />
                    ) : (
                      <Info
                        sx={{ color: 'text.disabled', width: 64, height: 64 }}
                      />
                    )}
                    <Typography>{food.name}</Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    {food.description || t('food.noDescription')}
                  </Typography>
                </TableCell>
                <TableCell align="center" sx={{ width: '100px' }}>
                  <Tooltip title={!isAdmin ? t('food.loginRequired') : ''}>
                    <span>
                      <Checkbox
                        checked={food.active}
                        onChange={() => isAdmin && toggleMutation.mutate(food.id)}
                        color="primary"
                        disabled={!isAdmin}
                      />
                    </span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};
