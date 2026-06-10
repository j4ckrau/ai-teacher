import { useState, useEffect } from 'react';
import { useTuringSocket } from './hooks/useTuringSocket';
import FocusView from './components/FocusView';
import BreakOverlay from './components/BreakOverlay';
import LearningMap from './components/LearningMap';
import { BookOpen, GraduationCap, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'lesson'>('dashboard');
  const [lessonTitle, setLessonTitle] = useState<string | null>(null);
  
  // Hardcoded student ID for testing
  const { chatHistory, systemAlert, isConnected, sendMessage, setChatHistory } = useTuringSocket('student_beta_1');

  // Browser History Support (Back Button)
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      if (event.state?.view) {
        setCurrentView(event.state.view);
      } else {
        setCurrentView('dashboard');
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const startLesson = (lessonId: string) => {
    setLessonTitle(lessonId); 
    setCurrentView('lesson');
    setChatHistory([]); // Clear chat for new lesson
    
    // Push state for back button support
    window.history.pushState({ view: 'lesson', lessonId }, '', `/lesson/${lessonId}`);
    
    sendMessage({
      type: 'start_lesson',
      concept_id: lessonId
    });
  };

  const navigateToDashboard = () => {
    setCurrentView('dashboard');
    window.history.pushState({ view: 'dashboard' }, '', '/');
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 overflow-x-hidden">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <GraduationCap className="text-blue-600 w-8 h-8" />
            <h1 className="text-xl font-bold tracking-tight">TuringEd</h1>
          </div>
          
          <nav className="flex items-center gap-2 text-sm text-slate-500">
            <button 
              onClick={navigateToDashboard}
              className={`hover:text-blue-600 transition ${currentView === 'dashboard' ? 'text-blue-600 font-medium' : ''}`}
            >
              Dashboard
            </button>
            {currentView === 'lesson' && (
              <>
                <ChevronRight size={14} className="opacity-30" />
                <span className="text-slate-900 font-medium truncate max-w-[150px]">
                  {lessonTitle}
                </span>
              </>
            )}
          </nav>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-semibold">Alex Johnson</p>
            <p className="text-xs text-slate-500">8th Grade • Mastery: 82%</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold border-2 border-white shadow-sm">
            AJ
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentView}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {currentView === 'dashboard' ? (
              <div className="space-y-6">
                <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm bg-gradient-to-br from-white to-blue-50/30">
                  <h2 className="text-3xl font-extrabold mb-2 tracking-tight">Welcome back, Alex! 👋</h2>
                  <p className="text-slate-600 text-lg">Your next recommended lesson is <strong>Variables on Both Sides</strong>. Explore your map to begin.</p>
                </div>
                
                <LearningMap onLessonSelect={startLesson} />
              </div>
            ) : (
              <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl overflow-hidden min-h-[80vh]">
                <div className="bg-slate-900 px-8 py-4 flex justify-between items-center text-white">
                  <h2 className="font-bold flex items-center gap-3">
                    <BookOpen size={20} className="text-blue-400" />
                    Lesson Session
                  </h2>
                  <button 
                    onClick={navigateToDashboard}
                    className="text-xs font-bold uppercase tracking-widest bg-white/10 hover:bg-white/20 px-4 py-2 rounded-full transition-all border border-white/10"
                  >
                    Exit Lesson
                  </button>
                </div>
                
                <FocusView 
                  chatHistory={chatHistory} 
                  sendMessage={sendMessage} 
                  isConnected={isConnected} 
                />
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      <BreakOverlay systemAlert={systemAlert} />
      
      {/* Global Status Bar */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 px-4 py-2 flex justify-between items-center text-[10px] text-slate-400 uppercase tracking-widest">
        <div className="flex gap-4">
          <span>System: Online</span>
          <span>BKT Engine: Active</span>
          <span>Curriculum: Neo4j Connected</span>
        </div>
        <div>
          © 2026 TuringEd Autonomous Systems
        </div>
      </footer>
    </div>
  );
}

export default App;
