import React, { useState, useRef } from 'react';
import './App.css';

const API_BASE = `http://${window.location.hostname}:8000`;

function App() {
  const [activeService, setActiveService] = useState('dashboard');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [error, setError] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [lastDocumentId, setLastDocumentId] = useState(null);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizResult, setQuizResult] = useState(null);
  const [serviceStatus, setServiceStatus] = useState(null);
  const audioRef = useRef(null);

  // Periodic health check for Phase 3
  React.useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/services/status`);
        if (res.ok) {
          const data = await res.ok ? await res.json() : null;
          if (data) setServiceStatus(data.services);
        }
      } catch (e) {
        console.error("Health check failed:", e);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  const services = [
    { id: 'stt', name: 'Speech to Text', icon: '🎙️', desc: 'Convert speech to text instantly' },
    { id: 'tts', name: 'Text to Speech', icon: '🔊', desc: 'Convert text to natural speech' },
    { id: 'documents', name: 'Document Reader', icon: '📄', desc: 'Analyze and extract info from documents' },
    { id: 'chat', name: 'Chat AI', icon: '🤖', desc: 'Smart AI assistant for learning and Q&A' },
    { id: 'quiz', name: 'Quiz Gen', icon: '📝', desc: 'Generate quizzes from educational materials' },
  ];

  const handleAction = async (service, endpoint, body = null, isFile = false) => {
    setLoading(true);
    setResult(null);
    setError(null);
    setAudioUrl(null);

    try {
      const options = {
        method: 'POST',
      };

      if (isFile) {
        options.body = body;
      } else if (body) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(body);
      }

      console.log(`Calling: ${API_BASE}/${service}/${endpoint}`);
      const response = await fetch(`${API_BASE}/${service}/${endpoint}`, options);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log("Response:", data);
      setResult(data);

      // Handle TTS audio
      if (service === 'tts' && data.audio_url) {
        const fullAudioUrl = `${API_BASE}${data.audio_url.replace('/api/tts', '/tts')}`;
        setAudioUrl(fullAudioUrl);
      }

      // Save document ID for quiz
      if (service === 'documents' && data.id) {
        setLastDocumentId(data.id);
      }

      // Handle chat
      if (service === 'chat' && data.response) {
        setChatMessages(prev => [...prev,
        { role: 'user', content: body.message },
        { role: 'assistant', content: data.response }
        ]);
      }

      // Reset quiz state on new quiz
      if (service === 'quiz' && endpoint === 'generate') {
        setQuizAnswers({});
        setQuizSubmitted(false);
        setQuizResult(null);
      }

    } catch (err) {
      console.error("Error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQuizSubmit = async () => {
    if (!result || !result.id) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/quiz/${result.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: quizAnswers })
      });

      if (response.ok) {
        const data = await response.json();
        setQuizResult(data);
        setQuizSubmitted(true);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderServiceView = () => {
    switch (activeService) {
      case 'stt':
        return (
          <div className="service-form glass-card">
            <h3>🎙️ Upload Audio for Transcription</h3>
            <p className="hint">Upload WAV or MP3 to convert to text</p>
            <input type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg" onChange={(e) => {
              if (e.target.files[0]) {
                const formData = new FormData();
                formData.append('file', e.target.files[0]);
                formData.append('language', 'en'); // Default to English
                handleAction('stt', 'transcribe', formData, true);
              }
            }} />
            {loading && <p className="loading">⏳ Analyzing audio file...</p>}
            {error && <p className="error">❌ {error}</p>}
            {result && (
              <div className="result-box">
                <h4>📝 Transcription Result:</h4>
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.8' }}>{result.text}</p>
                {result.confidence > 0 && (
                  <p className="confidence">Confidence: {(result.confidence * 100).toFixed(0)}%</p>
                )}
              </div>
            )}
          </div>
        );

      case 'tts':
        return (
          <div className="service-form glass-card">
            <h3>🔊 Text to Speech Synthesis</h3>
            <textarea
              placeholder="Enter text here... (English or Arabic)"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              rows={5}
            />
            <div className="btn-row">
              <button className="btn-primary" onClick={() => handleAction('tts', 'synthesize', { text: inputText, language: 'en' })}>
                🎵 Generate English Audio
              </button>
              <button className="btn-secondary" onClick={() => handleAction('tts', 'synthesize', { text: inputText, language: 'ar' })}>
                🎵 Generate Arabic Audio
              </button>
            </div>
            {loading && <p className="loading">⏳ Generating audio file...</p>}
            {error && <p className="error">❌ {error}</p>}
            {result && (
              <div className="result-box">
                <p>✅ {result.message}</p>
                {audioUrl && (
                  <div className="audio-player">
                    <h4>🎧 Listen to Audio:</h4>
                    <audio ref={audioRef} controls autoPlay src={audioUrl}>
                      Your browser does not support the audio element.
                    </audio>
                    <a href={audioUrl} download className="download-btn">📥 Download MP3</a>
                  </div>
                )}
              </div>
            )}
          </div>
        );

      case 'documents':
        return (
          <div className="service-form glass-card">
            <h3>📄 Upload Document for Analysis</h3>
            <p className="hint">Upload PDF, DOCX, or TXT to extract and analyze text</p>
            <input type="file" accept=".pdf,.doc,.docx,.txt" onChange={(e) => {
              if (e.target.files[0]) {
                const formData = new FormData();
                formData.append('file', e.target.files[0]);
                handleAction('documents', 'upload', formData, true);
              }
            }} />
            {loading && <p className="loading">⏳ Analyzing document...</p>}
            {error && <p className="error">❌ {error}</p>}
            {result && (
              <div className="result-box">
                <div style={{ whiteSpace: 'pre-wrap' }}>{result.summary}</div>
                {result.id && (
                  <div className="doc-actions">
                    <p className="success-msg">✅ Document saved! You can now generate a quiz from it.</p>
                    <button className="btn-primary" onClick={() => {
                      setActiveService('quiz');
                      setResult(null);
                    }}>
                      📝 Go to Quiz Gen
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        );

      case 'chat':
        return (
          <div className="chat-interface glass-card">
            <h3>🤖 Smart AI Assistant</h3>
            <div className="chat-window">
              {chatMessages.length === 0 && (
                <p className="chat-hint">Type "hello" or "help" to start!</p>
              )}
              {chatMessages.map((msg, i) => (
                <div key={i} className={`chat-bubble ${msg.role}`}>
                  <strong>{msg.role === 'user' ? '👤 You' : '🤖 Assistant'}:</strong>
                  <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                </div>
              ))}
              {loading && <p className="loading">⏳ AI is typing...</p>}
              {error && <p className="error">❌ {error}</p>}
            </div>
            <div className="chat-input-row">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Type your message here..."
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && inputText.trim()) {
                    handleAction('chat', 'message', { message: inputText });
                    setInputText("");
                  }
                }}
              />
              <button onClick={() => {
                if (inputText.trim()) {
                  handleAction('chat', 'message', { message: inputText });
                  setInputText("");
                }
              }}>Send</button>
            </div>
          </div>
        );

      case 'quiz':
        return (
          <div className="service-form glass-card">
            <h3>📝 Create a Quiz</h3>

            {!result && (
              <div className="quiz-options">
                {lastDocumentId && (
                  <div className="doc-linked">
                    <p>📄 Document found!</p>
                    <button className="btn-primary" onClick={() =>
                      handleAction('quiz', 'generate', { document_id: lastDocumentId, num_questions: 5 })
                    }>
                      Create Quiz from Document 📄
                    </button>
                  </div>
                )}
                <button className="btn-secondary" onClick={() =>
                  handleAction('quiz', 'generate', { topic: 'general', num_questions: 5 })
                }>
                  Create General Quiz 📋
                </button>
              </div>
            )}

            {loading && <p className="loading">⏳ Generating questions...</p>}
            {error && <p className="error">❌ {error}</p>}

            {result && result.questions && !quizSubmitted && (
              <div className="quiz-container">
                {result.source_document && (
                  <p className="quiz-source">📄 This quiz is based on your uploaded document</p>
                )}

                {result.questions.map((q, i) => (
                  <div key={i} className="quiz-question">
                    <p><strong>Q{q.id}:</strong> {q.question}</p>
                    <ul className="quiz-options-list">
                      {q.options.map((opt, j) => (
                        <li key={j}
                          className={quizAnswers[q.id] === opt ? 'selected' : ''}
                          onClick={() => setQuizAnswers({ ...quizAnswers, [q.id]: opt })}>
                          <input
                            type="radio"
                            name={`q${q.id}`}
                            checked={quizAnswers[q.id] === opt}
                            onChange={() => setQuizAnswers({ ...quizAnswers, [q.id]: opt })}
                          />
                          {opt}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}

                <button className="btn-primary submit-quiz" onClick={handleQuizSubmit}>
                  Submit Answers ✓
                </button>
              </div>
            )}

            {quizSubmitted && quizResult && (
              <div className="quiz-results">
                <h4>{quizResult.feedback}</h4>
                <p className="score">
                  Result: {quizResult.score} / {quizResult.total}
                  ({quizResult.percentage.toFixed(0)}%)
                </p>

                <div className="answers-review">
                  {quizResult.details && quizResult.details.map((d, i) => (
                    <div key={i} className={`answer-item ${d.is_correct ? 'correct' : 'wrong'}`}>
                      <p><strong>Q{d.question_id}:</strong> {d.question}</p>
                      <p>Your answer: {d.your_answer || 'No answer'} {d.is_correct ? '✓' : '✗'}</p>
                      {!d.is_correct && <p className="correct-ans">Correct answer: {d.correct_answer}</p>}
                      {d.explanation && <p className="explanation">💡 {d.explanation}</p>}
                    </div>
                  ))}
                </div>

                <button className="btn-secondary" onClick={() => {
                  setResult(null);
                  setQuizAnswers({});
                  setQuizSubmitted(false);
                  setQuizResult(null);
                }}>
                  New Quiz
                </button>
              </div>
            )}
          </div>
        );

      default:
        return <p>Service under construction...</p>;
    }
  };

  return (
    <div className="app-container">
      <nav className="navbar">
        <h1 className="gradient-text">Cloud Learning Platform ☁️</h1>
        <div className="nav-links">
          <button onClick={() => { setActiveService('dashboard'); setChatMessages([]); setResult(null); setError(null); setAudioUrl(null); }}>
            Home
          </button>
        </div>
      </nav>

      <main>
        {activeService === 'dashboard' ? (
          <>
            <div className="dashboard-grid">
              {services.map(service => (
                <div key={service.id} className="glass-card" onClick={() => setActiveService(service.id)}>
                  <div className="service-icon">{service.icon}</div>
                  <h2>{service.name}</h2>
                  <p>{service.desc}</p>
                  <button className="btn-primary mt-4">Start</button>
                </div>
              ))}
            </div>

            {/* Phase 3 Status Monitor */}
            <div className="status-monitor glass-card mt-8">
              <h3>🌐 System Health Monitor</h3>
              <div className="status-table-wrapper">
                <table className="status-table">
                  <thead>
                    <tr>
                      <th>Service Name</th>
                      <th>Status</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {services.map(s => (
                      <tr key={s.id}>
                        <td>{s.name}</td>
                        <td>
                          <span className={`status-pill ${serviceStatus && serviceStatus[s.id] ? serviceStatus[s.id].status : 'unknown'}`}>
                            {serviceStatus && serviceStatus[s.id] ? serviceStatus[s.id].status.toUpperCase() : 'CHECKING...'}
                          </span>
                        </td>
                        <td>Microservice</td>
                      </tr>
                    ))}
                    <tr>
                      <td>API Gateway</td>
                      <td><span className="status-pill healthy">OPERATIONAL</span></td>
                      <td>Gateway Root</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : (
          <div className="service-view">
            <button onClick={() => { setActiveService('dashboard'); setChatMessages([]); setResult(null); setError(null); setAudioUrl(null); }} className="back-btn">
              ← Back to Home
            </button>
            {renderServiceView()}
          </div>
        )}
      </main>

      <footer className="footer">
        <p>© 2025 Cloud Learning Platform | Built with FastAPI, Docker, and Kafka</p>
      </footer>
    </div>
  );
}

export default App;
