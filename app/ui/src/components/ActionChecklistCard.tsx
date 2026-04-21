import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

type ActionChecklistCardProps = {
  title: string;
  intro?: string;
  steps: string[];
  actions?: ReactNode;
};

export function ActionChecklistCard({
  title,
  intro,
  steps,
  actions,
}: ActionChecklistCardProps) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <div>
            <Typography variant="h6" sx={{ mb: intro ? 0.75 : 0 }}>
              {title}
            </Typography>
            {intro ? (
              <Typography variant="body2" color="text.secondary">
                {intro}
              </Typography>
            ) : null}
          </div>
          <Stack component="ol" spacing={1} sx={{ m: 0, pl: 2.5 }}>
            {steps.map((step) => (
              <Typography component="li" key={step} variant="body2">
                {step}
              </Typography>
            ))}
          </Stack>
          {actions}
        </Stack>
      </CardContent>
    </Card>
  );
}
