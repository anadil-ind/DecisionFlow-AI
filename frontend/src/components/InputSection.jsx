import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  FileText,
  X,
  ArrowRight,
  Sparkles,
  AlertCircle,
  FileSpreadsheet,
  Image as ImageIcon,
  ZoomIn,
  Plus,
  Info
} from 'lucide-react';

const SAMPLES = [
  {
    name: 'Scholarship Renewal Notice',
    category: 'Academic',
    text: `OFFICIAL NOTIFICATION - ACADEMIC YEAR 2026-27

Subject: Mandatory Submission of Scholarship Renewal Dossier

All recipients of the Merit-Cum-Means University Scholarship must submit their complete renewal applications on or before September 30, 2026. 

Requirements:
1. Students must upload certified copies of their latest semester marksheet (minimum 7.5 CGPA required).
2. An updated Family Income Certificate verified by the revenue authority (issued after April 1, 2026) must be attached.
3. Bank passbook front page showing IFSC and Account Number matching student registration.
4. Late submissions will not be entertained and will result in permanent forfeiture of scholarship disbursements.`,
  },
  {
    name: 'Annual Security & Compliance Audit',
    category: 'Corporate Compliance',
    text: `URGENT COMPLIANCE DIRECTIVE: Q4-2026

To: All Department Leads and External Contractors
Deadline: November 15, 2026
Priority: High

In accordance with global ISO/SOC2 security frameworks, all internal units and vendors must complete the Annual Security & Data Privacy Compliance Review.

Required Actions:
- Complete the mandatory 45-minute Security Awareness Refresher module via the employee portal.
- Submit the signed Vendor Risk Assessment questionnaire.
- Upload current SOC2 Type II compliance audit reports and proof of active Cyber Liability Insurance.
- Verify two-factor authentication (2FA) enforcement across all departmental service accounts.
Failure to comply before the deadline will lead to immediate suspension of system access privileges.`,
  },
  {
    name: 'Office Equipment Relocation Notice',
    category: 'Operations',
    text: `MEMORANDUM: Headquarters Relocation & IT Asset Handover

Please be advised that Floor 4 operations will be transitioning to the West Wing by October 20, 2026. 
Employees should back up all local workstation data to cloud drives.
IT department will issue equipment handover slips starting October 15. Please ensure all borrowed peripherals and monitors are tagged properly.`,
  },
];

const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.webp'];
const MAX_IMAGES = 5;

export default function InputSection({
  onAnalyzeUnified,
  onAnalyzeText,
  onAnalyzePdf,
  isAnalyzing = false,
}) {
  const [activeTab, setActiveTab] = useState('files'); // 'files' | 'text'
  const [selectedPdf, setSelectedPdf] = useState(null);
  const [selectedImages, setSelectedImages] = useState([]); // array of { file, previewUrl, id }
  const [previewModalImage, setPreviewModalImage] = useState(null);
  const [textInput, setTextInput] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);
  const [validationError, setValidationError] = useState('');

  const fileInputRef = useRef(null);

  // Clean up object URLs on unmount
  useEffect(() => {
    return () => {
      selectedImages.forEach((img) => URL.revokeObjectURL(img.previewUrl));
    };
  }, [selectedImages]);

  // File size formatter
  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Helper to validate and append files
  const processIncomingFiles = (fileList) => {
    setValidationError('');
    const files = Array.from(fileList || []);
    if (files.length === 0) return;

    let newPdf = selectedPdf;
    const newImages = [...selectedImages];

    for (const file of files) {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setValidationError(
          `Unsupported file type "${file.name}". Supported: PDF, PNG, JPG, JPEG, WEBP.`
        );
        return;
      }

      if (ext === '.pdf') {
        newPdf = file;
      } else {
        if (newImages.length >= MAX_IMAGES) {
          setValidationError(`A maximum of ${MAX_IMAGES} images is supported.`);
          break;
        }
        // Avoid duplicate by name + size
        const isDuplicate = newImages.some(
          (img) => img.file.name === file.name && img.file.size === file.size
        );
        if (!isDuplicate) {
          newImages.push({
            file,
            previewUrl: URL.createObjectURL(file),
            id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
          });
        }
      }
    }

    setSelectedPdf(newPdf);
    setSelectedImages(newImages);
  };

  // Drag and drop handlers
  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processIncomingFiles(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processIncomingFiles(e.target.files);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemovePdf = () => {
    setSelectedPdf(null);
    setValidationError('');
  };

  const handleRemoveImage = (idToRemove) => {
    setSelectedImages((prev) => {
      const target = prev.find((img) => img.id === idToRemove);
      if (target) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return prev.filter((img) => img.id !== idToRemove);
    });
    setValidationError('');
  };

  const handleSampleClick = (sampleText) => {
    setTextInput(sampleText);
    setValidationError('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError('');

    if (activeTab === 'files') {
      const hasPdf = !!selectedPdf;
      const hasImages = selectedImages.length > 0;

      if (!hasPdf && !hasImages) {
        setValidationError('Please upload a PDF document or at least one image to analyze.');
        return;
      }

      if (onAnalyzeUnified) {
        onAnalyzeUnified({
          pdf: selectedPdf,
          images: selectedImages.map((img) => img.file),
        });
      } else if (hasPdf && !hasImages && onAnalyzePdf) {
        onAnalyzePdf(selectedPdf);
      }
    } else {
      if (!textInput.trim()) {
        setValidationError('Please enter or paste text to analyze.');
        return;
      }
      if (onAnalyzeUnified) {
        onAnalyzeUnified({ text: textInput });
      } else if (onAnalyzeText) {
        onAnalyzeText(textInput);
      }
    }
  };

  const hasFiles = !!selectedPdf || selectedImages.length > 0;
  const canSubmit = activeTab === 'files' ? hasFiles : !!textInput.trim();

  return (
    <div className="card input-section-card" style={{ padding: '1.5rem' }}>
      {/* Tab Switcher */}
      <div className="tabs-header">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'files' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('files');
            setValidationError('');
          }}
        >
          <UploadCloud size={17} />
          Upload Document or Image
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'text' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('text');
            setValidationError('');
          }}
        >
          <FileText size={17} />
          Paste Text / Notice
        </button>
      </div>

      {/* Validation Error Banner */}
      {validationError && (
        <div className="alert-banner" style={{ marginBottom: '1.25rem' }}>
          <AlertCircle size={18} className="alert-icon" />
          <div>
            <div className="alert-title">Input Notice</div>
            <div className="alert-text">{validationError}</div>
          </div>
        </div>
      )}

      {/* ── UNIFIED FILE UPLOAD TAB (PDF + Images) ── */}
      {activeTab === 'files' && (
        <div className="files-upload-flow">
          {/* Main Dropzone */}
          <div
            className={`dropzone ${isDragActive ? 'drag-active' : ''} ${hasFiles ? 'dropzone--compact' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
              multiple
              style={{ display: 'none' }}
              onChange={handleFileInputChange}
            />
            <div className="dropzone-icon-box">
              <UploadCloud size={hasFiles ? 22 : 28} />
            </div>
            <div className="dropzone-prompt">
              {hasFiles ? (
                <span>Click or drag to add more images / PDF</span>
              ) : (
                <span>Upload Document or Image</span>
              )}
            </div>
            <div className="dropzone-subtext">
              Supported: <strong>PDF, PNG, JPG, JPEG, WEBP</strong> (up to 1 PDF + 5 images)
            </div>
          </div>

          {/* Helper Note */}
          <div className="upload-helper-note">
            <Info size={14} className="helper-info-icon" />
            <span>Add images when they contain important information that the document text alone cannot capture.</span>
          </div>

          {/* Selected Files Section */}
          {hasFiles && (
            <div className="selected-files-section">
              <div className="section-label" style={{ marginBottom: '0.625rem' }}>
                SELECTED FOR ANALYSIS ({ (selectedPdf ? 1 : 0) + selectedImages.length })
              </div>

              <div className="selected-cards-grid">
                {/* PDF Card */}
                {selectedPdf && (
                  <div className="file-preview-card pdf-card">
                    <div className="file-card-icon pdf-icon">
                      <FileSpreadsheet size={22} />
                    </div>
                    <div className="file-card-meta">
                      <div className="file-card-title" title={selectedPdf.name}>
                        {selectedPdf.name}
                      </div>
                      <div className="file-card-badge-row">
                        <span className="file-type-pill">PDF Document</span>
                        <span className="file-size-text">{formatFileSize(selectedPdf.size)}</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-remove-card"
                      onClick={handleRemovePdf}
                      title="Remove PDF"
                      aria-label="Remove PDF"
                    >
                      <X size={16} />
                    </button>
                  </div>
                )}

                {/* Images Cards */}
                {selectedImages.map((img) => (
                  <div key={img.id} className="file-preview-card image-card">
                    {/* Clickable Thumbnail */}
                    <div
                      className="image-card-thumb-wrap"
                      onClick={() =>
                        setPreviewModalImage({
                          previewUrl: img.previewUrl,
                          name: img.file.name,
                          size: formatFileSize(img.file.size),
                        })
                      }
                      title="Click to preview enlarged"
                    >
                      <img
                        src={img.previewUrl}
                        alt={img.file.name}
                        className="image-card-thumb"
                      />
                      <div className="thumb-zoom-overlay">
                        <ZoomIn size={16} />
                      </div>
                    </div>

                    <div className="file-card-meta">
                      <div className="file-card-title" title={img.file.name}>
                        {img.file.name}
                      </div>
                      <div className="file-card-badge-row">
                        <span className="file-type-pill image-pill">Image</span>
                        <span className="file-size-text">{formatFileSize(img.file.size)}</span>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="btn-remove-card"
                      onClick={() => handleRemoveImage(img.id)}
                      title="Remove Image"
                      aria-label="Remove Image"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── PASTE TEXT TAB (PRESERVED) ── */}
      {activeTab === 'text' && (
        <div>
          <div className="text-input-wrapper">
            <textarea
              className="analysis-textarea"
              placeholder="Paste raw notice, circular, company memo, or email instructions here..."
              value={textInput}
              onChange={(e) => {
                setTextInput(e.target.value);
                setValidationError('');
              }}
              rows={7}
            />
            <div className="textarea-footer">
              <span>Plain text input</span>
              <span>{textInput.length} characters</span>
            </div>
          </div>

          {/* Quick 1-Click Samples for instant demonstration */}
          <div className="samples-container">
            <div className="samples-label">
              <Sparkles size={13} />
              Quick Demo Samples (1-Click Fill):
            </div>
            <div className="samples-buttons">
              {SAMPLES.map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="sample-chip"
                  onClick={() => handleSampleClick(sample.text)}
                >
                  <FileText size={12} />
                  {sample.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Submit Action Button */}
      <div style={{ marginTop: '1.5rem' }}>
        <button
          type="button"
          id="btn-analyze-submit"
          className="btn-primary"
          onClick={handleSubmit}
          disabled={!canSubmit || isAnalyzing}
        >
          <Sparkles size={18} />
          <span>
            {activeTab === 'files'
              ? selectedPdf && selectedImages.length > 0
                ? 'Analyze PDF + Images with Cortex AI'
                : selectedPdf
                ? 'Analyze PDF Document with Cortex AI'
                : selectedImages.length > 0
                ? `Analyze ${selectedImages.length} Image${selectedImages.length > 1 ? 's' : ''} with Cortex AI`
                : 'Analyze with Cortex AI'
              : 'Analyze Text with Cortex AI'}
          </span>
          <ArrowRight size={17} />
        </button>
      </div>

      {/* ── IMAGE ENLARGED PREVIEW MODAL (LIGHTBOX) ── */}
      {previewModalImage && (
        <div
          className="modal-backdrop"
          onClick={() => setPreviewModalImage(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="modal-box image-lightbox-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="lightbox-header">
              <div className="lightbox-meta">
                <span className="lightbox-title">{previewModalImage.name}</span>
                <span className="lightbox-size">{previewModalImage.size}</span>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setPreviewModalImage(null)}
                aria-label="Close image preview"
              >
                <X size={18} />
              </button>
            </div>
            <div className="lightbox-image-wrap">
              <img
                src={previewModalImage.previewUrl}
                alt={previewModalImage.name}
                className="lightbox-img"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
