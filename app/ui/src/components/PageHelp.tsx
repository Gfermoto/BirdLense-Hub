import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';
import { PageHeader } from './PageHeader';

export interface HelpDetail {
  title: string;
  content: string;
}

export interface PageHelpProps {
  title: string;
  description?: string;
  details?: HelpDetail[];
  dialogMaxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  actions?: ReactNode;
  titleVariant?: 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
}

export interface PageHelpConfig {
  configKey:
    | 'overview'
    | 'food'
    | 'timeline'
    | 'videoDetails'
    | 'unknowns'
    | 'migrationCalendar'
    | 'library';
  dialogMaxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
}

export const PageHelp = (
  props: PageHelpProps | (PageHelpConfig & { title?: never; description?: never; details?: never }),
) => {
  const { t } = useTranslation();
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleOpenDialog = () => setDialogOpen(true);
  const handleCloseDialog = () => setDialogOpen(false);

  const isConfigKey = 'configKey' in props && props.configKey;
  const configKey = isConfigKey ? props.configKey : null;

  let title: string;
  let description: string | undefined;
  let details: HelpDetail[] | undefined;
  const dialogMaxWidth = props.dialogMaxWidth ?? 'sm';
  const actions = 'actions' in props ? props.actions : undefined;
  const titleVariant = 'titleVariant' in props ? props.titleVariant : undefined;

  if (configKey) {
    const helpData = t(`help.${configKey}`, { returnObjects: true }) as {
      title: string;
      description: string;
      details: HelpDetail[];
    };
    title = helpData?.title ?? '';
    description = helpData?.description;
    details = Array.isArray(helpData?.details) ? helpData.details : undefined;
  } else {
    title = (props as PageHelpProps).title;
    description = (props as PageHelpProps).description;
    details = (props as PageHelpProps).details;
  }

  const dialogTitleId = `help-dialog-${(title || configKey || 'help').toLowerCase().replace(/\s+/g, '-')}`;
  const dialogDescriptionId = `${dialogTitleId}-description`;

  return (
    <Box component="section" sx={{ mb: 3 }}>
      <PageHeader
        title={title}
        description={description}
        actions={actions}
        onHelpClick={handleOpenDialog}
        helpTooltip={t('common.clickForHelp')}
        helpAriaLabel={t('common.helpAbout', { title })}
        titleVariant={titleVariant ?? 'h3'}
      />
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        aria-labelledby={dialogTitleId}
        aria-describedby={dialogDescriptionId}
        maxWidth={dialogMaxWidth}
        fullWidth
      >
        <DialogTitle id={dialogTitleId}>{title}</DialogTitle>
        <DialogContent>
          <DialogContentText id={dialogDescriptionId}>
            {description}
          </DialogContentText>
          {details && details.length > 0 && (
            <Box component="dl" sx={{ mt: 2 }}>
              {details.map((detail, index) => (
                <Box key={index} sx={{ mb: 2 }}>
                  <Typography
                    component="dt"
                    variant="subtitle2"
                    color="primary"
                    gutterBottom
                  >
                    {detail.title}
                  </Typography>
                  <Typography component="dd" variant="body2" sx={{ m: 0 }} style={{ whiteSpace: 'pre-line' }}>
                    {detail.content}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t('common.close')}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
