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
import Avatar from '@mui/material/Avatar';
import Info from '@mui/icons-material/Info';
import Tooltip from '@mui/material/Tooltip';
import { resolveImageUrl, fetchBirdFood, toggleBirdFood } from '../../api/api';
import { BirdFood } from '../../types';
import { PageHelp } from '../../components/PageHelp';
import { foodHelpConfig } from '../../page-help-config';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';

export const FoodManagement = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { isAdmin } = useProtectedArea();
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
                    {food.image_url ? (
                      <Avatar
                        src={resolveImageUrl(food.image_url)}
                        alt={food.name}
                        variant="rounded"
                        sx={{ width: 64, height: 64 }}
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
