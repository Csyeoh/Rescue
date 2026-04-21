'use client';
import { useState, useRef } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

export default function SurvivorMic({ survivorId, onIntelReceived }: { survivorId: number, onIntelReceived: (intel: any) => void }) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const mediaRecorder = useRef<MediaRecorder | null>(null);
    const audioChunks = useRef<BlobPart[]>([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });

            mediaRecorder.current.ondataavailable = (event) => {
                if (event.data.size > 0) audioChunks.current.push(event.data);
            };

            mediaRecorder.current.onstop = async () => {
                setIsProcessing(true);
                const audioBlob = new Blob(audioChunks.current, { type: 'audio/webm' });
                const formData = new FormData();
                formData.append('file', audioBlob, 'transmission.webm');

                try {
                    const res = await fetch(`http://localhost:8000/api/survivors/${survivorId}/voice-intel`, {
                        method: 'POST',
                        body: formData,
                    });

                    if (!res.ok) {
                        const errData = await res.json();
                        console.error("Backend API Error:", errData);
                        alert(`API Error: ${errData.detail || "Failed to process audio"}`);
                        return; // Stop execution here
                    }
                    
                    const data = await res.json();
                    onIntelReceived(data.intel); // Pass the structured JSON up to the UI
                } catch (error) {
                    console.error("Intel extraction failed", error);
                } finally {
                    setIsProcessing(false);
                    audioChunks.current = [];
                }
            };

            audioChunks.current = [];
            mediaRecorder.current.start();
            setIsRecording(true);
        } catch (err) {
            console.error("Microphone access denied", err);
        }
    };

    const stopRecording = () => {
        if (mediaRecorder.current && isRecording) {
            mediaRecorder.current.stop();
            mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
            setIsRecording(false);
        }
    };

    return (
        <div className="absolute bottom-4 right-4 flex flex-col items-center p-3 bg-slate-900/80 backdrop-blur border border-slate-700 rounded-xl shadow-2xl z-50">
            <div className="text-xs text-slate-300 mb-2 uppercase tracking-wider font-semibold">
                {isProcessing ? "Analyzing Intel..." : "Survivor Transmission"}
            </div>
            <button
                onMouseDown={startRecording}
                onMouseUp={stopRecording}
                onMouseLeave={stopRecording} // Failsafe
                disabled={isProcessing}
                className={`p-4 rounded-full transition-all ${isRecording
                        ? 'bg-red-500/90 shadow-[0_0_15px_rgba(239,68,68,0.6)] animate-pulse'
                        : 'bg-emerald-600/90 hover:bg-emerald-500'
                    } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {isProcessing ? <Loader2 size={28} className="animate-spin text-white" /> :
                    isRecording ? <Square size={28} className="text-white" fill="currentColor" /> :
                        <Mic size={28} className="text-white" />}
            </button>
            <div className="mt-2 text-[10px] text-slate-400">Hold to speak</div>
        </div>
    );
}