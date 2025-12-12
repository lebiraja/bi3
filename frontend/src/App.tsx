import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout';
import { Dashboard, Upload, Jobs, JobDetail, Settings, LiveStream } from './pages';
import { ThemeProvider } from './contexts/ThemeContext';
import { SearchProvider } from './contexts/SearchContext';
import { NotificationProvider } from './contexts/NotificationContext';
import { ToastContainer } from './components/ui/ToastContainer';

function App() {
  return (
    <ThemeProvider>
      <NotificationProvider>
        <SearchProvider>
          <BrowserRouter>
            <ToastContainer />
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="upload" element={<Upload />} />
                <Route path="stream" element={<LiveStream />} />
                <Route path="jobs" element={<Jobs />} />
                <Route path="jobs/:jobId" element={<JobDetail />} />
                <Route path="settings" element={<Settings />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </SearchProvider>
      </NotificationProvider>
    </ThemeProvider>
  );
}

export default App;
