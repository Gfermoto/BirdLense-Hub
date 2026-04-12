import React from 'react';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import type { Settings } from '../../../types';
import { GeneralConnectionAccordion } from './GeneralConnectionAccordion';
import { GeneralPerformanceAccordion } from './GeneralPerformanceAccordion';
import { GeneralSecurityAccordion } from './GeneralSecurityAccordion';
import { GeneralYamlBackupAccordion } from './GeneralYamlBackupAccordion';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  /** Маскированный YAML — оператор и админ */
  yamlSafeExportEnabled?: boolean;
  /** Полный YAML и импорт — только админ (при двух паролях) */
  yamlAdminBackupEnabled?: boolean;
};

export function GeneralSection({
  form,
  yamlSafeExportEnabled = false,
  yamlAdminBackupEnabled = false,
}: Props) {
  return (
    <>
      <GeneralConnectionAccordion form={form} />
      <GeneralPerformanceAccordion form={form} />
      <GeneralSecurityAccordion form={form} />
      {yamlSafeExportEnabled || yamlAdminBackupEnabled ? (
        <GeneralYamlBackupAccordion
          yamlSafeExportEnabled={yamlSafeExportEnabled}
          yamlAdminBackupEnabled={yamlAdminBackupEnabled}
        />
      ) : null}
    </>
  );
}
