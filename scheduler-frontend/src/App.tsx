import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Employees from './pages/Employees'
import Schedule from './pages/Schedule'
import CsvUpload from './pages/CsvUpload'
import Constraints from './pages/Constraints'
import AiAssistant from './pages/AiAssistant'
import './App.css'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/employees" element={<Employees />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/csv-upload" element={<CsvUpload />} />
        <Route path="/constraints" element={<Constraints />} />
        <Route path="/ai-assistant" element={<AiAssistant />} />
      </Route>
    </Routes>
  )
}

export default App
