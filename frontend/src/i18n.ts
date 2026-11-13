// Every piece of text on screen, in Kannada, Hindi and English. The whole
// interface follows the language the user picked on the Home screen.

import type { DocumentType, ErrorKind, Language } from './api'

const kn = {
  tagline: 'ಬಿಲ್ ಅಥವಾ ಪತ್ರದ ಫೋಟೋ ತೆಗೆಯಿರಿ. ನಾನು ಓದಿ ಹೇಳುತ್ತೇನೆ.',
  scan: 'ಕಾಗದದ ಫೋಟೋ ತೆಗೆಯಿರಿ',
  gallery: 'ಗ್ಯಾಲರಿಯಿಂದ ಆರಿಸಿ',
  history: 'ಹಿಂದಿನ ಕಾಗದಗಳು',
  language: 'ಭಾಷೆ',
  home: 'ಮುಖಪುಟ',
  newScan: 'ಹೊಸ ಕಾಗದ',
  pleaseWait: 'ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಕಾಯಿರಿ…',
  stepSending: 'ಫೋಟೋ ಕಳುಹಿಸುತ್ತಿದೆ',
  stepReading: 'ಕಾಗದ ಓದುತ್ತಿದೆ',
  stepSpeaking: 'ಧ್ವನಿ ಸಿದ್ಧವಾಗುತ್ತಿದೆ',
  amountDue: 'ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ',
  dueDate: 'ಕೊನೆಯ ದಿನಾಂಕ',
  daysLeft: (n: number) => (n === 1 ? 'ಇನ್ನು ಒಂದು ದಿನ ಬಾಕಿ' : `ಇನ್ನು ${n} ದಿನ ಬಾಕಿ`),
  dueToday: 'ಇಂದೇ ಕೊನೆಯ ದಿನ',
  overdue: 'ದಿನಾಂಕ ಮುಗಿದಿದೆ',
  listen: 'ಕೇಳಿ',
  listenAgain: 'ಮತ್ತೆ ಕೇಳಿ',
  stop: 'ನಿಲ್ಲಿಸಿ',
  ask: 'ಪ್ರಶ್ನೆ ಕೇಳಿ',
  askHint: 'ಒತ್ತಿ, ಯಾವುದೇ ಭಾಷೆಯಲ್ಲಿ ಮಾತನಾಡಿ, ಮತ್ತೆ ಒತ್ತಿ',
  hearIn: 'ಯಾವ ಭಾಷೆಯಲ್ಲಿ ಕೇಳಬೇಕು?',
  preparing: 'ಸಿದ್ಧವಾಗುತ್ತಿದೆ…',
  recording: 'ಕೇಳುತ್ತಿದ್ದೇನೆ… ಮುಗಿದ ಮೇಲೆ ಒತ್ತಿ',
  done: 'ಮುಗಿಯಿತು',
  thinking: 'ಉತ್ತರ ಹುಡುಕುತ್ತಿದೆ…',
  youAsked: 'ನೀವು ಕೇಳಿದ್ದು',
  tooShort: 'ತುಂಬಾ ಚಿಕ್ಕದಾಯಿತು. ಮಾತನಾಡಿ, ನಂತರ ಒತ್ತಿ.',
  micDenied: 'ಮೈಕ್ರೊಫೋನ್ ಬಳಸಲು ಅನುಮತಿ ಕೊಡಿ.',
  retakePhoto: 'ಮತ್ತೆ ಫೋಟೋ ತೆಗೆಯಿರಿ',
  tryAgain: 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
  historyEmpty: 'ಇನ್ನೂ ಯಾವ ಕಾಗದವೂ ಇಲ್ಲ.',
  unclearTitle: 'ಫೋಟೋ ಸ್ಪಷ್ಟವಾಗಿಲ್ಲ',
  unsupportedTitle: 'ಈ ಕಾಗದ ಓದಲು ಆಗುವುದಿಲ್ಲ',
  textSize: 'ಅಕ್ಷರದ ಗಾತ್ರ',
  normalText: 'ಸಾಮಾನ್ಯ',
  largeText: 'ದೊಡ್ಡದು',
  checkPaper: 'ಕೆಲವು ಭಾಗ ಸರಿಯಾಗಿ ಕಾಣಲಿಲ್ಲ. ಮೊತ್ತ ಮತ್ತು ದಿನಾಂಕವನ್ನು ಕಾಗದದಲ್ಲಿ ಒಮ್ಮೆ ನೋಡಿ.',
  micUnsupported: 'ಈ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಧ್ವನಿ ರೆಕಾರ್ಡ್ ಆಗುವುದಿಲ್ಲ. https ಲಿಂಕ್ ತೆರೆಯಿರಿ.',
  errors: {
    network: 'ಇಂಟರ್ನೆಟ್ ಸಂಪರ್ಕ ಇಲ್ಲ. ಪರಿಶೀಲಿಸಿ, ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
    busy: 'ಸೇವೆ ಈಗ ಕಾರ್ಯನಿರತವಾಗಿದೆ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಪ್ರಯತ್ನಿಸಿ.',
    generic: 'ಏನೋ ತಪ್ಪಾಯಿತು. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  } satisfies Record<ErrorKind, string>,
  types: {
    electricity_bill: 'ವಿದ್ಯುತ್ ಬಿಲ್',
    bank_letter: 'ಬ್ಯಾಂಕ್ ಪತ್ರ',
    official_notice: 'ಸರ್ಕಾರಿ ಸೂಚನೆ',
    other: 'ಇತರೆ ಕಾಗದ',
    unreadable: 'ಸ್ಪಷ್ಟವಾಗಿಲ್ಲ',
  } satisfies Record<DocumentType, string>,
  months: ['ಜನವರಿ', 'ಫೆಬ್ರವರಿ', 'ಮಾರ್ಚ್', 'ಏಪ್ರಿಲ್', 'ಮೇ', 'ಜೂನ್', 'ಜುಲೈ', 'ಆಗಸ್ಟ್', 'ಸೆಪ್ಟೆಂಬರ್', 'ಅಕ್ಟೋಬರ್', 'ನವೆಂಬರ್', 'ಡಿಸೆಂಬರ್'],
}

const hi: typeof kn = {
  tagline: 'बिल या चिट्ठी की फ़ोटो लीजिए। हम पढ़कर सुनाएँगे।',
  scan: 'काग़ज़ की फ़ोटो लें',
  gallery: 'गैलरी से चुनें',
  history: 'पुराने काग़ज़',
  language: 'भाषा',
  home: 'होम',
  newScan: 'नया काग़ज़',
  pleaseWait: 'कृपया थोड़ा इंतज़ार करें…',
  stepSending: 'फ़ोटो भेजी जा रही है',
  stepReading: 'काग़ज़ पढ़ा जा रहा है',
  stepSpeaking: 'आवाज़ तैयार हो रही है',
  amountDue: 'चुकाने की रकम',
  dueDate: 'आख़िरी तारीख़',
  daysLeft: (n: number) => (n === 1 ? 'बस एक दिन बाकी' : `${n} दिन बाकी`),
  dueToday: 'आज आख़िरी दिन है',
  overdue: 'तारीख़ निकल गई',
  listen: 'सुनें',
  listenAgain: 'फिर से सुनें',
  stop: 'रोकें',
  ask: 'सवाल पूछें',
  askHint: 'दबाएँ, किसी भी भाषा में बोलें, फिर दबाएँ',
  hearIn: 'किस भाषा में सुनें?',
  preparing: 'तैयार हो रहा है…',
  recording: 'सुन रहे हैं… बोलकर दबाएँ',
  done: 'हो गया',
  thinking: 'जवाब ढूँढा जा रहा है…',
  youAsked: 'आपने पूछा',
  tooShort: 'बहुत छोटा था। बोलिए, फिर दबाइए।',
  micDenied: 'माइक्रोफ़ोन इस्तेमाल करने की अनुमति दें।',
  retakePhoto: 'फिर से फ़ोटो लें',
  tryAgain: 'फिर से कोशिश करें',
  historyEmpty: 'अभी कोई काग़ज़ नहीं है।',
  unclearTitle: 'फ़ोटो साफ़ नहीं है',
  unsupportedTitle: 'यह काग़ज़ पढ़ा नहीं जा सकता',
  textSize: 'अक्षर का आकार',
  normalText: 'सामान्य',
  largeText: 'बड़ा',
  checkPaper: 'कुछ हिस्सा साफ़ नहीं दिखा। रकम और तारीख़ काग़ज़ पर एक बार देख लें।',
  micUnsupported: 'इस ब्राउज़र में आवाज़ रिकॉर्ड नहीं हो सकती। https लिंक खोलें।',
  errors: {
    network: 'इंटरनेट नहीं है। जाँचकर फिर से कोशिश करें।',
    busy: 'सेवा अभी व्यस्त है। थोड़ी देर बाद कोशिश करें।',
    generic: 'कुछ गड़बड़ हो गई। कृपया फिर से कोशिश करें।',
  },
  types: {
    electricity_bill: 'बिजली का बिल',
    bank_letter: 'बैंक का पत्र',
    official_notice: 'सरकारी सूचना',
    other: 'अन्य काग़ज़',
    unreadable: 'साफ़ नहीं',
  },
  months: ['जनवरी', 'फ़रवरी', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अगस्त', 'सितंबर', 'अक्टूबर', 'नवंबर', 'दिसंबर'],
}

export type Strings = typeof kn

const en: typeof kn = {
  tagline: 'Take a photo of a bill or letter. We will read it out to you.',
  scan: 'Take a photo of the paper',
  gallery: 'Choose from gallery',
  history: 'Earlier papers',
  language: 'Language',
  home: 'Home',
  newScan: 'New paper',
  pleaseWait: 'Please wait a moment…',
  stepSending: 'Sending the photo',
  stepReading: 'Reading the paper',
  stepSpeaking: 'Getting the voice ready',
  amountDue: 'Amount to pay',
  dueDate: 'Last date',
  daysLeft: (n: number) => (n === 1 ? 'Only 1 day left' : `${n} days left`),
  dueToday: 'Today is the last day',
  overdue: 'The date has passed',
  listen: 'Listen',
  listenAgain: 'Listen again',
  stop: 'Stop',
  ask: 'Ask a question',
  askHint: 'Tap, speak in any language, tap again',
  hearIn: 'Hear it in',
  preparing: 'Getting it ready…',
  recording: 'Listening… tap when you finish',
  done: 'Done',
  thinking: 'Finding the answer…',
  youAsked: 'You asked',
  tooShort: 'That was too short. Speak, then tap.',
  micDenied: 'Please allow the microphone.',
  retakePhoto: 'Take the photo again',
  tryAgain: 'Try again',
  historyEmpty: 'No papers yet.',
  unclearTitle: 'The photo is not clear',
  unsupportedTitle: 'This paper cannot be read',
  textSize: 'Text size',
  normalText: 'Normal',
  largeText: 'Large',
  checkPaper: 'Some parts were hard to read. Please check the amount and date on the paper.',
  micUnsupported: 'Recording does not work in this browser. Please open the https link.',
  errors: {
    network: 'No internet. Please check and try again.',
    busy: 'The service is busy. Please try again in a little while.',
    generic: 'Something went wrong. Please try again.',
  },
  types: {
    electricity_bill: 'Electricity bill',
    bank_letter: 'Bank letter',
    official_notice: 'Government notice',
    other: 'Other paper',
    unreadable: 'Not clear',
  },
  months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
}

export const STRINGS: Record<Language, Strings> = { 'kn-IN': kn, 'hi-IN': hi, 'en-IN': en }

// "₹1,179" with Indian digit grouping (1,23,456).
export function formatRupees(amount: number): string {
  return '₹' + amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

// "2026-11-19" -> "19 ನವೆಂಬರ್ 2026"
export function formatDate(isoDate: string, t: Strings): string {
  return `${formatDayMonth(isoDate, t)} ${isoDate.slice(0, 4)}`
}

// "2026-11-19" -> "19 ನವೆಂಬರ್"
export function formatDayMonth(isoDate: string, t: Strings): string {
  const [, month, day] = isoDate.split('-').map(Number)
  return `${day} ${t.months[month - 1]}`
}

// Whole days from today until the due date (negative if it has passed).
export function daysUntil(isoDate: string): number {
  const [year, month, day] = isoDate.split('-').map(Number)
  const due = new Date(year, month - 1, day)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86_400_000)
}
