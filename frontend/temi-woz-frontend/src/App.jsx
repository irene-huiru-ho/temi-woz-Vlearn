// src/App.jsx
import { Routes, Route } from 'react-router-dom'
import WizardPage from './pages/Wizard'
import ParticipantPage from './pages/Participant'
import RobotPage from './pages/Robot'
import Dashboard from './pages/Dashboard'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/wizard" element={<WizardPage />} />
      <Route path="/participant" element={<ParticipantPage />} />
      <Route path="/robot" element={<RobotPage />} />
    </Routes>
  )
}

export default App
