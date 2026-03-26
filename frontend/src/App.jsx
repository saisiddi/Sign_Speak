import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom';
import Header from './components/Header';
import { useWebSocket } from './hooks/useWebSocket';
import Live from './pages/Live';
import Snippets from './pages/Snippets';
import Settings from './pages/Settings';
import './App.css';

function Layout() {
  const wsSource = useWebSocket();

  return (
    <div className="app-container">
      <Header isConnected={wsSource.isConnected} />
      <main className="main-content">
        <Outlet context={wsSource} />
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Live />} />
          <Route path="snippets" element={<Snippets />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
