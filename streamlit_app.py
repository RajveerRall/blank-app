import streamlit as st
import pysrt
import json
import re
import string
import io
import os

# Function to convert time to "HH:MM:SS" format
def time_to_hms(time_obj):
    return f"{time_obj.hours:02}:{time_obj.minutes:02}:{time_obj.seconds:02}"

# Function to clean text by removing extra spaces and formatting
def clean_text(text):
    # Remove extra spaces
    text = ' '.join(text.strip().split())
    # Remove space before punctuation
    text = re.sub(r'\s+([{}])'.format(re.escape(string.punctuation + '।')), r'\1', text)
    return text.strip()

# Function to process subtitles and merge them into complete sentences
def process_subtitles(subs):
    sentences = []
    buffer = ''
    start_time = None
    end_time = None

    for sub in subs:
        text = clean_text(sub.text)
        if not text:
            continue

        if start_time is None:
            start_time = sub.start

        buffer += ' ' + text
        buffer = buffer.strip()
        end_time = sub.end  # Update end time to current subtitle's end time

        # Check for sentence-ending punctuation
        if any(buffer.endswith(punct) for punct in ['.', '!', '?', '।']):
            sentences.append({
                'text': buffer,
                'start_time': start_time,
                'end_time': end_time
            })
            buffer = ''
            start_time = None
            end_time = None

    # Handle any remaining text
    if buffer:
        sentences.append({
            'text': buffer,
            'start_time': start_time,
            'end_time': end_time
        })

    return sentences

def create_end_time_dict(sentences):
    end_time_dict = {}
    for sentence in sentences:
        end_time_str = time_to_hms(sentence['end_time'])
        if end_time_str not in end_time_dict:
            end_time_dict[end_time_str] = []
        end_time_dict[end_time_str].append(sentence)
    return end_time_dict

def align_sentences_by_end_time(eng_sentences, hin_sentences):
    eng_end_times = create_end_time_dict(eng_sentences)
    hin_end_times = create_end_time_dict(hin_sentences)

    # Get the sorted list of matching end times
    common_end_times = sorted(set(eng_end_times.keys()).intersection(hin_end_times.keys()))

    aligned_pairs = []
    eng_start_idx = 0
    hin_start_idx = 0

    for end_time in common_end_times:
        # Merge English sentences up to the current end time
        eng_sents_to_merge = []
        while eng_start_idx < len(eng_sentences) and time_to_hms(eng_sentences[eng_start_idx]['end_time']) != end_time:
            eng_sents_to_merge.append(eng_sentences[eng_start_idx]['text'])
            eng_start_idx += 1
        # Include the sentence with the matching end time
        if eng_start_idx < len(eng_sentences):
            eng_sents_to_merge.append(eng_sentences[eng_start_idx]['text'])
            eng_start_idx += 1

        # Merge Hindi sentences up to the current end time
        hin_sents_to_merge = []
        while hin_start_idx < len(hin_sentences) and time_to_hms(hin_sentences[hin_start_idx]['end_time']) != end_time:
            hin_sents_to_merge.append(hin_sentences[hin_start_idx]['text'])
            hin_start_idx += 1
        # Include the sentence with the matching end time
        if hin_start_idx < len(hin_sentences):
            hin_sents_to_merge.append(hin_sentences[hin_start_idx]['text'])
            hin_start_idx += 1

        # Merge sentences
        eng_text = ' '.join(eng_sents_to_merge)
        hin_text = ' '.join(hin_sents_to_merge)

        aligned_pairs.append({
            'source': eng_text.strip(),
            'target': hin_text.strip()
        })

    return aligned_pairs

def process_file_pair(eng_file_content, hin_file_content):
    # Load subtitles from file content
    english_subs = pysrt.from_string(eng_file_content.read().decode('utf-8'), encoding='utf-8')
    hindi_subs = pysrt.from_string(hin_file_content.read().decode('utf-8'), encoding='utf-8')

    # Process subtitles to merge into sentences
    english_sentences = process_subtitles(english_subs)
    hindi_sentences = process_subtitles(hindi_subs)

    # Align sentences by matching end times
    aligned_pairs = align_sentences_by_end_time(english_sentences, hindi_sentences)

    return aligned_pairs

# Streamlit UI
st.title("Subtitle Alignment Tool")

uploaded_files = st.file_uploader("Upload English and Hindi SRT files", type="srt", accept_multiple_files=True)

if uploaded_files:
    if st.button("Process Files"):
        st.write("Processing files...")
        # Separate English and Hindi files
        eng_files = {}
        hin_files = {}
        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            # Remove language tags to get base name
            base_name = filename.replace('[English]', '').replace('[Hindi]', '').strip()
            # Remove extra spaces and brackets
            base_name = re.sub(r'\s+\[.*?\]', '', base_name).strip()
            if '[English]' in filename:
                eng_files[base_name] = uploaded_file
            elif '[Hindi]' in filename:
                hin_files[base_name] = uploaded_file

        # Match files and process
        all_aligned_pairs = []
        for base_name in eng_files:
            if base_name in hin_files:
                eng_file = eng_files[base_name]
                hin_file = hin_files[base_name]
                st.write(f"Processing: {base_name}")
                aligned_pairs = process_file_pair(eng_file, hin_file)
                all_aligned_pairs.extend(aligned_pairs)
            else:
                st.warning(f"No matching Hindi file for {base_name}")

        # Save all aligned pairs to a JSON Lines file
        output = io.StringIO()
        for pair in all_aligned_pairs:
            json_line = json.dumps(pair, ensure_ascii=False)
            output.write(json_line + '\n')
        output.seek(0)

        # Provide download link
        st.success("Processing complete!")
        st.download_button(
            label="Download Aligned Dataset",
            data=output.getvalue(),
            file_name="aligned_dataset.jsonl",
            mime="text/plain",
        )
else:
    st.info("Please upload English and Hindi SRT files to begin.")
