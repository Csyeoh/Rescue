import { useState, useEffect, useCallback } from 'react';

export const useVoiceCommand = () => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [recognition, setRecognition] = useState<any>(null);

  useEffect(() => {
    // Ensure we are only running this on the client side (Next.js SSR safety)
    if (typeof window !== 'undefined') {
      // Grab the standard or webkit-prefixed API (Chrome/Edge use webkit)
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      
      if (SpeechRecognition) {
        const rec = new SpeechRecognition();
        rec.continuous = false; // Stops automatically after the user finishes a sentence
        rec.interimResults = false; // We only want the final, polished sentence
        rec.lang = 'en-US'; // Change this if you are giving commands in another language

        rec.onresult = (event: any) => {
          const text = event.results[0][0].transcript;
          setTranscript(text);
        };

        rec.onend = () => {
          setIsListening(false);
        };

        rec.onerror = (event: any) => {
          console.error("Speech Recognition Error: ", event.error);
          setIsListening(false);
        };

        setRecognition(rec);
      } else {
        console.warn("Web Speech API is not supported in this browser.");
      }
    }
  }, []);

  const startListening = useCallback(() => {
    if (recognition) {
      try {
        setTranscript(''); // Clear old transcript
        recognition.start();
        setIsListening(true);
      } catch (e) {
        console.error("Microphone is already listening.");
      }
    }
  }, [recognition]);

  const stopListening = useCallback(() => {
    if (recognition) {
      recognition.stop();
      setIsListening(false);
    }
  }, [recognition]);

  return {
    isListening,
    transcript,
    startListening,
    stopListening,
    hasSupport: !!recognition
  };
};