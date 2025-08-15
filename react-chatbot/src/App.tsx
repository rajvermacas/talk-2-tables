import React from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import ChatInterface from './components/ChatInterface';

function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gradient-to-br from-gray-100 via-gray-50 to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
        <ChatInterface />
      </div>
    </ThemeProvider>
  );
}

export default App;
