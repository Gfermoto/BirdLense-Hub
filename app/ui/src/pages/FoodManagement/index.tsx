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
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import Info from '@mui/icons-material/Info';
import { resolveImageUrl, fetchBirdFood, toggleBirdFood } from '../../api/api';
import { BirdFood } from '../../types';
import { PageHelp } from '../../components/PageHelp';
import { foodHelpConfig } from '../../page-help-config';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';

export const FoodManagement = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { isAdmin, canEdit } = useProtectedArea();
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
      {canEdit && <PageHelp {...foodHelpConfig} />}
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
                    {food.image_url && !brokenImages[food.id] ? (
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
                  <span>
                    <Checkbox
                      checked={food.active}
                      onChange={() => isAdmin && toggleMutation.mutate(food.id)}
                      color="primary"
                      disabled={!isAdmin}
                    />
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};
