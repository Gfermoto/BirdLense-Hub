import Box from '@mui/material/Box';
import { AutomationDiagnosticsCard, AutomationFusionCard, AutomationMaintenanceCard } from './AutomationPanels';

export function AutomationCard() {
  return (
    <Box display="grid" gap={2}>
      <AutomationFusionCard />
      <AutomationDiagnosticsCard />
      <AutomationMaintenanceCard />
    </Box>
  );
}
