"""
Fixed, pre-written messages we speak instead of asking the LLM.

Writing these by hand means they are always polite, correct and identical. The
same text also gives the same TTS cache key, so each one costs a Gnani credit
only once.
"""

UNCLEAR_PHOTO = {
    "kn-IN": "ಕ್ಷಮಿಸಿ, ಈ ಫೋಟೋ ಸ್ಪಷ್ಟವಾಗಿ ಓದಲು ಆಗುತ್ತಿಲ್ಲ. "
    "ದಯವಿಟ್ಟು ಒಳ್ಳೆಯ ಬೆಳಕಿನಲ್ಲಿ, ಕಾಗದ ಪೂರ್ತಿಯಾಗಿ ಕಾಣುವಂತೆ ಇನ್ನೊಮ್ಮೆ ಫೋಟೋ ತೆಗೆಯಿರಿ.",
    "hi-IN": "माफ़ कीजिए, यह फ़ोटो साफ़ नहीं पढ़ी जा रही है। "
    "कृपया अच्छी रोशनी में, पूरा काग़ज़ दिखे ऐसे, फिर से फ़ोटो लीजिए।",
    "en-IN": "Sorry, this photo is not clear enough to read. "
    "Please take another photo in good light, with the whole paper showing.",
}

UNSUPPORTED_DOCUMENT = {
    "kn-IN": "ಕ್ಷಮಿಸಿ, ಸದ್ಯಕ್ಕೆ ವಿದ್ಯುತ್ ಬಿಲ್, ಬ್ಯಾಂಕ್ ಪತ್ರ ಮತ್ತು ಸರ್ಕಾರಿ ಸೂಚನೆಗಳನ್ನು ಮಾತ್ರ ಓದಬಹುದು.",
    "hi-IN": "माफ़ कीजिए, अभी केवल बिजली का बिल, बैंक का पत्र और सरकारी सूचना ही पढ़ी जा सकती है।",
    "en-IN": "Sorry, right now only electricity bills, bank letters and government notices can be read.",
}

# Gnani STT returned nothing: silence, or the recording was too quiet.
DIDNT_HEAR = {
    "kn-IN": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಇನ್ನೊಮ್ಮೆ ಕೇಳಿ.",
    "hi-IN": "माफ़ कीजिए, आपका सवाल ठीक से सुनाई नहीं दिया। कृपया फिर से पूछिए।",
    "en-IN": "Sorry, your question was not heard clearly. Please ask again.",
}

# The answer isn't in the document (or we couldn't answer it safely).
NOT_IN_DOCUMENT = {
    "kn-IN": "ಕ್ಷಮಿಸಿ, ಈ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರ ಈ ಕಾಗದದಲ್ಲಿ ಸಿಗಲಿಲ್ಲ.",
    "hi-IN": "माफ़ कीजिए, इस सवाल का जवाब इस काग़ज़ में नहीं मिला।",
    "en-IN": "Sorry, the answer to this question is not in this paper.",
}

# Added after the explanation when parts of the photo were hard to read.
CHECK_PAPER = {
    "kn-IN": "ಕೆಲವು ಭಾಗ ಸರಿಯಾಗಿ ಕಾಣಲಿಲ್ಲ. ಮೊತ್ತ ಮತ್ತು ದಿನಾಂಕವನ್ನು ಕಾಗದದಲ್ಲಿ ಒಮ್ಮೆ ನೋಡಿ.",
    "hi-IN": "कुछ हिस्सा साफ़ नहीं दिखा। रकम और तारीख़ काग़ज़ पर एक बार देख लें।",
    "en-IN": "Some parts were hard to read. Please check the amount and date on the paper.",
}
