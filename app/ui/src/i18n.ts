import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from '../locales/en.json';
import ru from '../locales/ru.json';
import de from '../locales/de.json';

const STORAGE_KEY = 'birdlense-lang';

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ru', label: 'Русский' },
  { code: 'de', label: 'Deutsch' },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]['code'];

const SUPPORTED_CODES = LANGUAGES.map((l) => l.code);

function resolveInitialLanguage(): LanguageCode {
  const saved = localStorage.getItem(STORAGE_KEY) as LanguageCode | null;
  if (saved && SUPPORTED_CODES.includes(saved)) return saved;
  const browserLang = (navigator.language || 'en').slice(0, 2).toLowerCase();
  if (SUPPORTED_CODES.includes(browserLang as LanguageCode)) {
    return browserLang as LanguageCode;
  }
  return 'en';
}

const initialLang = resolveInitialLanguage();

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
    de: { translation: de },
  },
  lng: initialLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export function setLanguage(code: LanguageCode) {
  i18n.changeLanguage(code);
  localStorage.setItem(STORAGE_KEY, code);
}
