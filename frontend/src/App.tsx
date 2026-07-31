import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout/Layout'
import { Dashboard } from './pages/Dashboard'
import { EngagementList } from './pages/Engagements/EngagementList'
import { EngagementCreate } from './pages/Engagements/EngagementCreate'
import { EngagementDetail } from './pages/Engagements/EngagementDetail'
import { DiscoveryScan } from './pages/Discovery/DiscoveryScan'
import { DiscoveryDegraded } from './pages/Discovery/DiscoveryDegraded'
import { HandshakeList } from './pages/Validation/HandshakeList'
import { HandshakeDetail } from './pages/Validation/HandshakeDetail'
import { ValidationPage } from './pages/Validation/ValidationPage'
import { ValidateCapture } from './pages/Validation/ValidateCapture'
import { JobList } from './pages/Cracking/JobList'
import { JobDetail } from './pages/Cracking/JobDetail'
import { CrackingResources } from './pages/Cracking/CrackingResources'
import { CrackingAnalyze } from './pages/Cracking/CrackingAnalyze'
import { FindingsList } from './pages/Findings/FindingsList'
import { FindingDetail } from './pages/Findings/FindingDetail'
import { FindingsCreatePage } from './pages/Findings/FindingsCreate'
import { ToolsCheck } from './pages/Tools/ToolsCheck'
import { EvidenceList } from './pages/Evidence/EvidenceList'
import { EvidenceDetail } from './pages/Evidence/EvidenceDetail'
import { JobsList } from './pages/Jobs/JobsList'
import { JobDetailPage } from './pages/Jobs/JobDetail'
import { InterfacesPage } from './pages/Interfaces/InterfacesPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          {/* Engagements */}
          <Route path="/engagements" element={<EngagementList />} />
          <Route path="/engagements/new" element={<EngagementCreate />} />
          <Route path="/engagements/:id" element={<EngagementDetail />} />
          {/* Discovery */}
          <Route path="/discovery" element={<DiscoveryScan />} />
          <Route path="/discovery/degraded" element={<DiscoveryDegraded />} />
          {/* Handshakes / Validation */}
          <Route path="/handshakes" element={<HandshakeList />} />
          <Route path="/handshakes/:id" element={<HandshakeDetail />} />
          <Route path="/validation" element={<ValidationPage />} />
          <Route path="/validation/validate" element={<ValidateCapture />} />
          {/* Cracking */}
          <Route path="/cracking" element={<JobList />} />
          <Route path="/cracking/:id" element={<JobDetail />} />
          <Route path="/cracking/resources" element={<CrackingResources />} />
          <Route path="/cracking/analyze/:artifactId" element={<CrackingAnalyze />} />
          {/* Findings */}
          <Route path="/findings" element={<FindingsList />} />
          <Route path="/findings/new" element={<FindingsCreatePage />} />
          <Route path="/findings/:id" element={<FindingDetail />} />
          {/* Evidence */}
          <Route path="/evidence" element={<EvidenceList />} />
          <Route path="/evidence/:id" element={<EvidenceDetail />} />
          {/* Jobs */}
          <Route path="/jobs" element={<JobsList />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          {/* Interfaces */}
          <Route path="/interfaces" element={<InterfacesPage />} />
          {/* Tools */}
          <Route path="/tools" element={<ToolsCheck />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
