import Box from '@mui/material/Box';
import {
  AutomationDiagnosticsCard,
  AutomationFusionCard,
  AutomationMaintenanceCard,
} from './AutomationPanels';
import { ProcessorWeightsCard } from './ProcessorWeightsCard';

export function AutomationCard() {
  return (
    <Box
      display="grid"
      gap={2}
      sx={{ minWidth: 0, maxWidth: '100%', width: '100%' }}
    >
      <ProcessorWeightsCard placement="systemWorkspace" />
      <AutomationFusionCard />
      <AutomationDiagnosticsCard />
      <AutomationMaintenanceCard />
    </Box>
  );
}
