import { useEffect, useMemo, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const companyAccounts = [
  { username: 'company', password: 'company123', role: 'company' },
]

const userAccounts = [
  { username: 'user', password: 'user123', role: 'user' },
]

function App() {
  const [session, setSession] = useState(null)
  const [activeTab, setActiveTab] = useState('login')
  const [error, setError] = useState('')

  const handleLogin = (username, password, role) => {
    const store = role === 'company' ? companyAccounts : userAccounts
    const account = store.find((item) => item.username === username && item.password === password)
    if (!account) {
      setError('Invalid credentials. Use the sample login provided.')
      return
    }
    setSession({ username, role })
    setActiveTab(role === 'company' ? 'company' : 'user')
    setError('')
  }

  const handleLogout = () => {
    setSession(null)
    setActiveTab('login')
  }

  return (
    <div className="page-shell">
      {!session ? (
        <main className="landing-grid">
          <section className="hero-panel">
            <div>
              <p className="eyebrow">MOSS Embedded Product Q&A</p>
              <h1>Company product upload → AI-powered user support</h1>
              <p className="subtitle">
                Upload a product manual, create a searchable knowledge base, and let end users ask questions about the product.
              </p>
            </div>
          </section>
          <LoginPanel onLogin={handleLogin} error={error} />
        </main>
      ) : (
        <main className="app-grid">
          <div className="workspace-shell">
            <div className="workspace-header">
              <div>
                <p className="workspace-label">Signed in as</p>
                <p className="workspace-user">{session.username} • {session.role}</p>
              </div>
              <button className="text-button" onClick={handleLogout}>Sign out</button>
            </div>
            {session.role === 'company' ? <CompanyWorkspace apiBase={API_BASE} /> : <UserWorkspace apiBase={API_BASE} />}
          </div>
        </main>
      )}
    </div>
  )
}

function LoginPanel({ onLogin, error }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('company')

  const submit = (event) => {
    event.preventDefault()
    onLogin(username.trim(), password.trim(), role)
  }

  return (
    <section className="panel card">
      <h2>Login to the MOSS portal</h2>
      <p className="panel-copy">Choose your role and sign in to access the company product upload or user product Q&A flows.</p>
      <form className="form-grid" onSubmit={submit}>
        <label className="wide-label">
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="company">Company</option>
            <option value="user">User</option>
          </select>
        </label>
        <label>
          Username
          <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="company or user" />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter password" />
        </label>
        {error && <div className="error-banner">{error}</div>}
        <button type="submit" className="primary-button">Sign in</button>
      </form>
      <div className="hint-block">
        <p><strong>Try:</strong></p>
        <p>Company login: <code>company / company123</code></p>
        <p>User login: <code>user / user123</code></p>
      </div>
    </section>
  )
}

function CompanyWorkspace({ apiBase }) {
  const [productId, setProductId] = useState('')
  const [productName, setProductName] = useState('')
  const [pdfFile, setPdfFile] = useState(null)
  const [status, setStatus] = useState('')
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)

  const loadProducts = async () => {
    setLoading(true)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 8000)
    try {
      const response = await fetch(`${apiBase}/products`, { signal: controller.signal })
      if (!response.ok) {
        throw new Error(`server responded with ${response.status}`)
      }
      const list = await response.json()
      setProducts(list)
    } catch (err) {
      console.error('Product load failed:', err)
      if (err.name === 'AbortError') {
        setStatus('Product load timeout')
      } else if (err instanceof TypeError) {
        setStatus(`Unable to load products: ${err.message}. Check that the backend is running at ${apiBase}`)
      } else {
        setStatus(`Unable to load products: ${err.message}`)
      }
    } finally {
      clearTimeout(timeoutId)
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  const uploadProduct = async (event) => {
    event.preventDefault()
    if (!productId || !productName || !pdfFile) {
      setStatus('Please complete all fields and attach a PDF manual.')
      return
    }

    const formData = new FormData()
    formData.append('product_id', productId)
    formData.append('product_name', productName)
    formData.append('pdf_manual', pdfFile)

    setLoading(true)
    setStatus('Uploading and indexing product manual...')
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 30000)
    try {
      const response = await fetch(`${apiBase}/products`, {
        method: 'POST',
        body: formData,
        signal: controller.signal
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Upload failed')
      }
      const result = await response.json()
      setStatus(`Product ${result.product_name} ingested successfully.`)
      setProductId('')
      setProductName('')
      setPdfFile(null)
      await loadProducts()
    } catch (err) {
      if (err.name === 'AbortError') {
        setStatus('Upload timeout')
      } else {
        setStatus(err.message)
      }
    } finally {
      clearTimeout(timeout)
      setLoading(false)
    }
  }

  return (
    <section className="workspace-panel">
      <div className="split-grid">
        <div className="panel card">
          <h2>Company product onboarding</h2>
          <p className="panel-copy">Upload a product manual PDF and register a product ID for MOSS embedding ingestion.</p>
          <form className="form-grid" onSubmit={uploadProduct}>
            <label>
              Product ID
              <input value={productId} onChange={(e) => setProductId(e.target.value)} placeholder="ex: motor-1001" />
            </label>
            <label>
              Product Name
              <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="ex: Smart Motor Drive" />
            </label>
            <label>
              PDF Manual
              <input type="file" accept="application/pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} />
            </label>
            {status && <div className="status-message">{status}</div>}
            {status?.includes('Unable to load products') && (
              <div className="status-message">Backend endpoint: {apiBase}</div>
            )}
            <button type="submit" className="primary-button" disabled={loading}>{loading ? 'Processing…' : 'Upload and Index'}</button>
          </form>
        </div>

        <div className="panel card">
          <h2>Registered products</h2>
          {loading && <p>Loading products…</p>}
          {!loading && products.length === 0 && <p>No products have been registered yet.</p>}
          <ul className="product-list">
            {products.map((product) => (
              <li key={product.product_id} className="product-item">
                <div>
                  <strong>{product.product_name}</strong>
                  <p className="micro">ID: {product.product_id}</p>
                </div>
                <div className="micro">Ingested: {product.ingested_at || 'unknown'}</div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}

function UserWorkspace({ apiBase }) {
  const [products, setProducts] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [message, setMessage] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [isRecording, setIsRecording] = useState(false)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const recognitionRef = useRef(null)

  const loadProducts = async () => {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 8000)
    try {
      const response = await fetch(`${apiBase}/products`, { signal: controller.signal })
      if (!response.ok) {
        throw new Error(`server responded with ${response.status}`)
      }
      const list = await response.json()
      setProducts(list)
      if (list.length && !selectedId) {
        setSelectedId(list[0].product_id)
      }
    } catch (err) {
      console.error('Product load failed:', err)
      if (err.name === 'AbortError') {
        setStatus('Product load timeout')
      } else if (err instanceof TypeError) {
        setStatus(`Unable to load products: ${err.message}. Check that the backend is running at ${apiBase}`)
      } else {
        setStatus(`Unable to load products: ${err.message}`)
      }
    } finally {
      clearTimeout(timeoutId)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  useEffect(() => {
    if (!imageFile) {
      setImagePreview(null)
      return
    }

    const previewUrl = URL.createObjectURL(imageFile)
    setImagePreview(previewUrl)
    return () => URL.revokeObjectURL(previewUrl)
  }, [imageFile])

  useEffect(() => {
    const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)
    if (!SpeechRecognition) {
      recognitionRef.current = null
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.maxAlternatives = 1
    recognition.continuous = false

    recognition.onresult = (event) => {
      const lastResult = event.results[event.results.length - 1]
      const transcript = lastResult?.[0]?.transcript?.trim() || ''
      if (!transcript) {
        setStatus('No speech transcript detected. Try again.')
        return
      }

      if (!lastResult.isFinal) {
        setStatus('Listening... ' + transcript)
        return
      }

      setMessage((prev) => (prev ? `${prev} ${transcript}` : transcript))
      setStatus('Voice input captured. Edit or send when ready.')
    }

    recognition.onspeechend = () => {
      recognition.stop()
    }

    recognition.onnomatch = () => {
      setStatus('No speech match found. Try again.')
      setIsRecording(false)
    }

    recognition.onerror = (event) => {
      setStatus(`Voice recognition error: ${event.error || 'unknown error'}`)
      setIsRecording(false)
    }

    recognition.onend = () => {
      setIsRecording(false)
      if (!message) {
        setStatus('Recording ended. Speak again or type your message.')
      }
    }

    recognitionRef.current = recognition
    return () => {
      recognition.stop?.()
    }
  }, [])

  useEffect(() => {
    setChatHistory([])
    setStatus('')
    setMessage('')
    setImageFile(null)
  }, [selectedId])

  const appendMessage = (role, content, imageUrl = null) => {
    setChatHistory((current) => [...current, { role, content: String(content), imageUrl }])
  }

  const submitQuestion = async (event) => {
    event.preventDefault()
    if (!selectedId || !message.trim()) {
      setStatus('Select a product and enter a question.')
      return
    }

    const userContent = message.trim()
    appendMessage('user', userContent, imagePreview)
    setMessage('')
    setStatus('Thinking through the manual…')

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 20000)
    try {
      let response
      if (imageFile) {
        const formData = new FormData()
        formData.append('messages', JSON.stringify([...chatHistory, { role: 'user', content: userContent }]))
        formData.append('product_image', imageFile)
        response = await fetch(`${apiBase}/products/${encodeURIComponent(selectedId)}/chat/photo`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        })
      } else {
        response = await fetch(`${apiBase}/products/${encodeURIComponent(selectedId)}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: [...chatHistory, { role: 'user', content: userContent }] }),
          signal: controller.signal,
        })
      }

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Chat request failed')
      }
      const result = await response.json()
      appendMessage('assistant', result.assistant || result.answer || 'No reply')
      setStatus('Response received.')
      setImageFile(null)
    } catch (err) {
      if (err.name === 'AbortError') {
        setStatus('Chat request timed out')
      } else {
        setStatus(err.message)
      }
    } finally {
      clearTimeout(timeoutId)
    }
  }

  const clearChat = () => {
    setChatHistory([])
    setMessage('')
    setImageFile(null)
    setStatus('Chat cleared.')
  }

  const handleImageChange = (event) => {
    const selected = event.target.files?.[0] || null
    setImageFile(selected)
  }

  const startRecording = () => {
    if (!recognitionRef.current) {
      setStatus('Voice input is not supported in this browser.')
      return
    }
    setStatus('Listening... speak clearly into your microphone.')
    setIsRecording(true)
    try {
      recognitionRef.current.start()
    } catch (error) {
      console.warn('Speech recognition start error:', error)
      setStatus('Unable to start voice recording. Try again.')
      setIsRecording(false)
    }
  }

  const stopRecording = () => {
    recognitionRef.current?.stop()
    setIsRecording(false)
    setStatus('Voice recording stopped.')
  }

  const recognitionSupported = typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)

  const availableProducts = useMemo(
    () => products.map((product) => ({ label: product.product_name, value: product.product_id })),
    [products],
  )

  return (
    <section className="workspace-panel">
      <div className="split-grid">
        <div className="panel card">
          <div className="chat-header">
            <div>
              <h2>User product Q&A</h2>
              <p className="panel-copy">Ask questions about the product manual.</p>
            </div>
            <button className="text-button" type="button" onClick={clearChat}>Clear chat</button>
          </div>

          <label>
            Product
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
              {availableProducts.map((product) => (
                <option key={product.value} value={product.value}>{product.label}</option>
              ))}
            </select>
          </label>

          <div className="chat-box">
            {chatHistory.length === 0 && <div className="chat-empty">No messages yet. Ask a question to begin.</div>}
            {chatHistory.map((item, index) => (
              <div key={`${item.role}-${index}`} className={`chat-message ${item.role}`}>
                <div className="chat-role">{item.role === 'assistant' ? 'Assistant' : 'You'}</div>
                {item.imageUrl && <img className="chat-image" src={item.imageUrl} alt="Uploaded" />}
                <div className="chat-content">{item.content}</div>
              </div>
            ))}
          </div>

          <form className="form-grid" onSubmit={submitQuestion}>
            <label>
              Message
              <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Type your question here." rows={4} />
            </label>
            <div className="voice-row">
              <button type="button" className="secondary-button" onClick={recognitionSupported ? (isRecording ? stopRecording : startRecording) : undefined}>
                {isRecording ? 'Stop recording' : 'Record voice'}
              </button>
              {!recognitionSupported && <span className="voice-hint">Voice-to-text not supported in this browser.</span>}
            </div>
            <label>
              Attach image
              <input type="file" accept="image/*" onChange={handleImageChange} />
            </label>
            {imagePreview && <img className="image-preview" src={imagePreview} alt="Preview" />}
            {status && <div className="status-message">{status}</div>}
            <button type="submit" className="primary-button">Send</button>
          </form>
        </div>
      </div>
    </section>
  )
}

export default App
