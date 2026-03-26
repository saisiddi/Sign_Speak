import { NavLink } from 'react-router-dom';

export default function Header({ isConnected }) {
  return (
    <header className="header-nav">
      <div className="logo">SignSpeak</div>
      <nav className="nav-links">
        <NavLink to="/" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>Live</NavLink>
        <NavLink to="/snippets" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>Snippets</NavLink>
        <NavLink to="/settings" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>Settings</NavLink>
      </nav>
      <div>
        <span className={isConnected ? "status-live" : "status-offline"}>
          {isConnected ? "LIVE" : "OFFLINE"}
        </span>
      </div>
    </header>
  );
}
