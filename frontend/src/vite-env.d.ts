/// <reference types="vite/client" />

type SpeechRecognitionAlternative = {
	transcript: string;
	confidence: number;
};

type SpeechRecognitionResult = {
	readonly isFinal: boolean;
	readonly length: number;
	item(index: number): SpeechRecognitionAlternative;
	[index: number]: SpeechRecognitionAlternative;
};

type SpeechRecognitionResultList = {
	readonly length: number;
	item(index: number): SpeechRecognitionResult;
	[index: number]: SpeechRecognitionResult;
};

type SpeechRecognitionEvent = {
	readonly resultIndex: number;
	readonly results: SpeechRecognitionResultList;
};

interface SpeechRecognition {
	continuous: boolean;
	interimResults: boolean;
	lang: string;
	onresult: ((event: SpeechRecognitionEvent) => void) | null;
	onerror: ((event: { error: string; message?: string }) => void) | null;
	onend: (() => void) | null;
	start(): void;
	stop(): void;
}

interface SpeechRecognitionConstructor {
	new (): SpeechRecognition;
}

interface Window {
	SpeechRecognition?: SpeechRecognitionConstructor;
	webkitSpeechRecognition?: SpeechRecognitionConstructor;
}
