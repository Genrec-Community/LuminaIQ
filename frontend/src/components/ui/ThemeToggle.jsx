import React from 'react';
import { useSettings } from '../../context/SettingsContext';
import { Sun, Moon } from 'lucide-react';
import { Button } from './Button';

export function ThemeToggle() {
  const { settings, updateSetting } = useSettings();

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => updateSetting('darkMode', !settings.darkMode)}
      title="Toggle theme"
    >
      {settings.darkMode ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
    </Button>
  );
}
