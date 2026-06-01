import { Routes, Route, NavLink } from 'react-router-dom'
import NewRun from './pages/NewRun'
import Results from './pages/Results'
import History from './pages/History'

function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <NavLink to="/" className="navbar-brand">✦ Marketing Agent</NavLink>
        <div className="navbar-links">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            New Run
          </NavLink>
          <NavLink
            to="/history"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            History
          </NavLink>
        </div>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<NewRun />} />
        <Route path="/run/:jobId" element={<Results />} />
        <Route path="/history" element={<History />} />
      </Routes>
    </>
  )
}
