/**
 * MultiFileProcessor - Global Multi-File Processing System
 * 
 * A reusable JavaScript module for handling multiple file uploads,
 * processing them sequentially, and tracking progress.
 * 
 * Usage:
 *   var processor = new MultiFileProcessor(options);
 *   processor.init();
 */

(function (global) {
    'use strict';

    /**
     * MultiFileProcessor Constructor
     * @param {Object} options - Configuration options
     */
    function MultiFileProcessor(options) {
        // Default options
        this.options = Object.assign({
            // Required: DOM element IDs
            uploadAreaId: 'upload-area',
            fileInputId: 'file-input',
            queueContainerId: 'file-queue',
            resultsContainerId: 'batch-results',
            convertBtnId: 'convert-btn',
            clearBtnId: 'clear-queue',

            // API endpoint
            apiUrl: '/api/convert/',

            // File configuration
            accept: '*/*',
            multiple: true,
            maxFiles: 50,
            maxFileSize: 500 * 1024 * 1024, // 500MB

            // Form data builder - override to add custom fields
            getFormData: function (file) { return {}; },

            // Response handler - override to extract download URL
            getDownloadUrl: function (response) { return response.download_url; },

            // File name for download
            getOutputFilename: function (file, response) {
                return file.name.replace(/\.[^/.]+$/, '') + '.' + (this.outputFormat || 'converted');
            },

            // History tracking
            historyEnabled: true,
            historyTool: 'File Converter',
            historyIcon: '📄',

            // Callbacks
            onFileAdded: null,
            onFileRemoved: null,
            onQueueUpdate: null,
            onProcessStart: null,
            onFileProcessing: null,
            onFileComplete: null,
            onFileError: null,
            onAllComplete: null,

            // UI text
            dropText: 'Drag & drop files here or click to select',
            dropHint: 'Select multiple files (Ctrl/Cmd + Click)',
            queueTitle: 'Files Queue',
            processingText: 'Processing...',
            completeText: 'Complete!',

            // Icons
            fileIcon: '📄',
            processingIcon: '⚙️',
            doneIcon: '✅',
            errorIcon: '❌',
            pendingIcon: '⏳'
        }, options);

        // State
        this.fileQueue = [];
        this.results = [];
        this.isProcessing = false;
        this.currentIndex = 0;
        this.aborted = false;

        // DOM elements (populated in init)
        this.elements = {};
    }

    /**
     * Initialize the processor
     */
    MultiFileProcessor.prototype.init = function () {
        var self = this;

        // Get DOM elements
        this.elements = {
            uploadArea: document.getElementById(this.options.uploadAreaId),
            fileInput: document.getElementById(this.options.fileInputId),
            queueContainer: document.getElementById(this.options.queueContainerId),
            resultsContainer: document.getElementById(this.options.resultsContainerId),
            convertBtn: document.getElementById(this.options.convertBtnId),
            clearBtn: document.getElementById(this.options.clearBtnId)
        };

        // Validate required elements
        if (!this.elements.uploadArea || !this.elements.fileInput) {
            console.error('MultiFileProcessor: Required elements not found');
            return;
        }

        // Set file input attributes
        if (this.options.multiple) {
            this.elements.fileInput.setAttribute('multiple', 'multiple');
        }
        if (this.options.accept) {
            this.elements.fileInput.setAttribute('accept', this.options.accept);
        }

        // Bind events
        this.bindEvents();

        // Initial UI state
        this.updateUI();

        return this;
    };

    /**
     * Bind all event handlers
     */
    MultiFileProcessor.prototype.bindEvents = function () {
        var self = this;

        // File input change
        this.elements.fileInput.addEventListener('change', function (e) {
            self.addFiles(e.target.files);
            e.target.value = ''; // Reset to allow same file selection
        });

        // Drag and drop
        this.elements.uploadArea.addEventListener('dragover', function (e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.add('drag-over');
        });

        this.elements.uploadArea.addEventListener('dragleave', function (e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');
        });

        this.elements.uploadArea.addEventListener('drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.remove('drag-over');
            self.addFiles(e.dataTransfer.files);
        });

        // Convert button
        if (this.elements.convertBtn) {
            this.elements.convertBtn.addEventListener('click', function (e) {
                if (!self.isProcessing && self.fileQueue.length > 0) {
                    // Don't prevent default - let form submit handler work if exists
                }
            });
        }

        // Clear button
        if (this.elements.clearBtn) {
            this.elements.clearBtn.addEventListener('click', function (e) {
                e.preventDefault();
                self.clearAll();
            });
        }

        // Prevent navigation during processing
        window.addEventListener('beforeunload', function (e) {
            if (self.isProcessing) {
                e.preventDefault();
                e.returnValue = 'Files are still being processed. Are you sure you want to leave?';
                return e.returnValue;
            }
        });
    };

    /**
     * Add files to the queue
     * @param {FileList} files - Files to add
     */
    MultiFileProcessor.prototype.addFiles = function (files) {
        var self = this;
        var added = 0;

        for (var i = 0; i < files.length; i++) {
            var file = files[i];

            // Check max files
            if (this.fileQueue.length >= this.options.maxFiles) {
                console.warn('Maximum files limit reached');
                break;
            }

            // Check file size
            if (file.size > this.options.maxFileSize) {
                console.warn('File too large: ' + file.name);
                continue;
            }

            // Check for duplicates
            var isDuplicate = this.fileQueue.some(function (f) {
                return f.file.name === file.name && f.file.size === file.size;
            });

            if (isDuplicate) {
                continue;
            }

            // Add to queue
            var queueItem = {
                id: Date.now() + '_' + i,
                file: file,
                status: 'pending', // pending, processing, done, error
                progress: 0,
                result: null,
                error: null
            };

            this.fileQueue.push(queueItem);
            added++;

            if (this.options.onFileAdded) {
                this.options.onFileAdded(queueItem, this.fileQueue);
            }
        }

        if (added > 0) {
            this.updateUI();
            if (this.options.onQueueUpdate) {
                this.options.onQueueUpdate(this.fileQueue);
            }
        }

        return added;
    };

    /**
     * Remove a file from the queue
     * @param {number} index - Index to remove
     */
    MultiFileProcessor.prototype.removeFile = function (index) {
        if (this.isProcessing) return;

        var removed = this.fileQueue.splice(index, 1)[0];

        if (removed && this.options.onFileRemoved) {
            this.options.onFileRemoved(removed, this.fileQueue);
        }

        this.updateUI();

        if (this.options.onQueueUpdate) {
            this.options.onQueueUpdate(this.fileQueue);
        }
    };

    /**
     * Clear all files from the queue
     */
    MultiFileProcessor.prototype.clearAll = function () {
        if (this.isProcessing) return;

        this.fileQueue = [];
        this.results = [];
        this.updateUI();

        // Hide results
        if (this.elements.resultsContainer) {
            this.elements.resultsContainer.style.display = 'none';
        }

        if (this.options.onQueueUpdate) {
            this.options.onQueueUpdate(this.fileQueue);
        }
    };

    /**
     * Start processing all files
     */
    MultiFileProcessor.prototype.startProcessing = async function () {
        if (this.isProcessing || this.fileQueue.length === 0) return;

        var self = this;
        this.isProcessing = true;
        this.aborted = false;
        this.currentIndex = 0;
        this.results = [];

        // Update button state
        this.setButtonLoading(true);

        if (this.options.onProcessStart) {
            this.options.onProcessStart(this.fileQueue);
        }

        // Process files sequentially
        for (var i = 0; i < this.fileQueue.length; i++) {
            if (this.aborted) break;

            this.currentIndex = i;
            var item = this.fileQueue[i];

            // Update status
            item.status = 'processing';
            this.updateQueueItemUI(i);

            if (this.options.onFileProcessing) {
                this.options.onFileProcessing(item, i, this.fileQueue);
            }

            try {
                var result = await this.processFile(item);
                item.status = 'done';
                item.result = result;
                this.results.push({
                    file: item.file,
                    downloadUrl: result.downloadUrl,
                    filename: result.filename
                });

                if (this.options.onFileComplete) {
                    this.options.onFileComplete(item, i, this.fileQueue);
                }
            } catch (error) {
                item.status = 'error';
                item.error = error.message || 'Processing failed';

                if (this.options.onFileError) {
                    this.options.onFileError(item, error, i, this.fileQueue);
                }
            }

            this.updateQueueItemUI(i);
        }

        // Done
        this.isProcessing = false;
        this.setButtonLoading(false);

        // Show results
        if (this.results.length > 0) {
            this.showResults();

            // Add to history
            if (this.options.historyEnabled && window.addToHistory) {
                window.addToHistory({
                    tool: this.options.historyTool,
                    icon: this.options.historyIcon,
                    fileName: this.results.length + ' files',
                    details: 'Batch conversion completed'
                });
            }
        }

        if (this.options.onAllComplete) {
            this.options.onAllComplete(this.results, this.fileQueue);
        }
    };

    /**
     * Process a single file
     * @param {Object} item - Queue item
     * @returns {Promise} - Resolves with result
     */
    MultiFileProcessor.prototype.processFile = function (item) {
        var self = this;

        return new Promise(function (resolve, reject) {
            var formData = new FormData();
            formData.append('file', item.file);

            // Add additional form fields
            var extraData = self.options.getFormData.call(self, item.file);
            for (var key in extraData) {
                if (extraData.hasOwnProperty(key)) {
                    formData.append(key, extraData[key]);
                }
            }

            fetch(self.options.apiUrl, {
                method: 'POST',
                body: formData
            })
                .then(async function (response) {
                    if (!response.ok) {
                        var data = await response.json().catch(function () { return {}; });
                        if (response.status === 413) {
                            throw new Error('File too large. Max limit is 500MB.');
                        }
                        if (response.status === 429) {
                            throw new Error('Rate limit exceeded. Try again later.');
                        }
                        if (response.status === 409) {
                            throw new Error('A similar job is already processing.');
                        }
                        throw new Error(data.error || data.details || 'Request failed (' + response.status + ')');
                    }

                    var contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        var data = await response.json();
                        // Check if job is async/pending
                        if (data.status === 'pending' || data.status === 'processing') {
                            data = await self.pollJob(data.id);
                        }

                        var downloadUrl = self.options.getDownloadUrl.call(self, data);
                        var filename = self.options.getOutputFilename.call(self, item.file, data);

                        return {
                            downloadUrl: downloadUrl,
                            filename: filename,
                            data: data
                        };
                    } else {
                        // Handle Blob response (Synchronous)
                        var blob = await response.blob();
                        var downloadUrl = URL.createObjectURL(blob);
                        var filename = self.options.getOutputFilename.call(self, item.file, {});

                        return {
                            downloadUrl: downloadUrl,
                            filename: filename,
                            data: { status: 'completed' }
                        };
                    }
                })
                .then(function (result) {
                    resolve(result);
                })
                .catch(function (error) {
                    reject(error);
                });
        });
    };

    /**
     * Poll job status until completion or failure
     * @param {string} jobId - Job ID to poll
     * @returns {Promise} - Resolves with final job data
     */
    MultiFileProcessor.prototype.pollJob = function (jobId) {
        var self = this;
        var attempts = 0;
        var maxAttempts = 300; // 10 minutes approx (2s interval)

        return new Promise(function (resolve, reject) {
            var interval = setInterval(function () {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(interval);
                    reject(new Error('Processing timed out'));
                    return;
                }

                fetch('/api/core/jobs/' + jobId + '/')
                    .then(function (res) { return res.json(); })
                    .then(function (job) {
                        if (job.status === 'completed') {
                            clearInterval(interval);
                            resolve(job);
                        } else if (job.status === 'failed') {
                            clearInterval(interval);
                            reject(new Error(job.error_message || 'Job failed'));
                        }
                        // Continue polling if pending/processing
                    })
                    .catch(function (err) {
                        // Ignore transient network errors, but stop on 404/500 if mostly persistent
                        console.warn('Poll error:', err);
                    });
            }, 2000);
        });
    };

    /**
     * Abort processing
     */
    MultiFileProcessor.prototype.abort = function () {
        this.aborted = true;
    };

    /**
     * Update the entire UI
     */
    MultiFileProcessor.prototype.updateUI = function () {
        this.renderQueue();
        this.updateButtonState();
    };

    /**
     * Render the file queue
     */
    MultiFileProcessor.prototype.renderQueue = function () {
        var self = this;

        if (!this.elements.queueContainer) return;

        if (this.fileQueue.length === 0) {
            this.elements.queueContainer.style.display = 'none';
            // Show upload content
            var uploadContent = this.elements.uploadArea.querySelector('.upload-content');
            if (uploadContent) uploadContent.style.display = 'block';
            return;
        }

        // Hide upload content, show queue
        var uploadContent = this.elements.uploadArea.querySelector('.upload-content');
        if (uploadContent) uploadContent.style.display = 'none';
        this.elements.queueContainer.style.display = 'block';

        // Update count
        var countEl = this.elements.queueContainer.querySelector('.batch-queue-count');
        if (countEl) countEl.textContent = this.fileQueue.length;

        // Render queue list
        var listEl = this.elements.queueContainer.querySelector('.batch-queue-list');
        if (!listEl) return;

        var html = '';
        this.fileQueue.forEach(function (item, index) {
            var statusClass = 'pending';
            var statusText = self.options.pendingIcon + ' Pending';

            if (item.status === 'processing') {
                statusClass = 'processing';
                statusText = self.options.processingIcon + ' Converting...';
            } else if (item.status === 'done') {
                statusClass = 'done';
                statusText = self.options.doneIcon + ' Done';
            } else if (item.status === 'error') {
                statusClass = 'error';
                statusText = self.options.errorIcon + ' Failed';
            }

            html += '<div class="batch-queue-item" data-index="' + index + '">' +
                '<div class="batch-queue-item-info">' +
                '<span class="batch-queue-item-icon">' + self.options.fileIcon + '</span>' +
                '<span class="batch-queue-item-name">' + self.escapeHtml(item.file.name) + '</span>' +
                '<span class="batch-queue-item-size">' + self.formatSize(item.file.size) + '</span>' +
                '</div>' +
                '<div class="batch-queue-item-status ' + statusClass + '">' + statusText + '</div>' +
                (self.isProcessing ? '' : '<button type="button" class="batch-queue-item-remove" data-index="' + index + '">&times;</button>') +
                '</div>';
        });

        listEl.innerHTML = html;

        // Bind remove buttons
        listEl.querySelectorAll('.batch-queue-item-remove').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                self.removeFile(parseInt(btn.dataset.index));
            });
        });
    };

    /**
     * Update a single queue item's UI
     * @param {number} index - Index of item
     */
    MultiFileProcessor.prototype.updateQueueItemUI = function (index) {
        var self = this;
        var listEl = this.elements.queueContainer.querySelector('.batch-queue-list');
        if (!listEl) return;

        var itemEl = listEl.querySelector('[data-index="' + index + '"]');
        if (!itemEl) return;

        var item = this.fileQueue[index];
        var statusEl = itemEl.querySelector('.batch-queue-item-status');

        if (statusEl) {
            var statusClass = 'pending';
            var statusText = this.options.pendingIcon + ' Pending';

            if (item.status === 'processing') {
                statusClass = 'processing';
                statusText = this.options.processingIcon + ' Converting...';
            } else if (item.status === 'done') {
                statusClass = 'done';
                statusText = this.options.doneIcon + ' Done';
            } else if (item.status === 'error') {
                statusClass = 'error';
                statusText = this.options.errorIcon + ' ' + (item.error || 'Failed');
            }

            statusEl.className = 'batch-queue-item-status ' + statusClass;
            statusEl.textContent = statusText;
        }
    };

    /**
     * Update convert button state
     */
    MultiFileProcessor.prototype.updateButtonState = function () {
        if (!this.elements.convertBtn) return;

        this.elements.convertBtn.disabled = this.fileQueue.length === 0 || this.isProcessing;
    };

    /**
     * Set button loading state
     * @param {boolean} loading - Is loading
     */
    MultiFileProcessor.prototype.setButtonLoading = function (loading) {
        if (!this.elements.convertBtn) return;

        if (loading) {
            this.elements.convertBtn.classList.add('processing');
            this.elements.convertBtn.disabled = true;
        } else {
            this.elements.convertBtn.classList.remove('processing');
            this.elements.convertBtn.disabled = false;
        }
    };

    /**
     * Show results
     */
    MultiFileProcessor.prototype.showResults = function () {
        if (!this.elements.resultsContainer || this.results.length === 0) return;

        var html = '';
        this.results.forEach(function (result) {
            html += '<div class="batch-result-item">' +
                '<span class="batch-result-name">' + result.filename + '</span>' +
                '<a href="' + result.downloadUrl + '" class="batch-result-download" download="' + result.filename + '">Download</a>' +
                '</div>';
        });

        var listEl = this.elements.resultsContainer.querySelector('.batch-results-list');
        if (listEl) {
            listEl.innerHTML = html;
        }

        this.elements.resultsContainer.style.display = 'block';
    };

    /**
     * Utility: Format file size
     * @param {number} bytes - Size in bytes
     * @returns {string} - Formatted size
     */
    MultiFileProcessor.prototype.formatSize = function (bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    };

    /**
     * Utility: Escape HTML
     * @param {string} str - String to escape
     * @returns {string} - Escaped string
     */
    MultiFileProcessor.prototype.escapeHtml = function (str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    /**
     * Get file count
     * @returns {number} - Number of files in queue
     */
    MultiFileProcessor.prototype.getFileCount = function () {
        return this.fileQueue.length;
    };

    /**
     * Get processing state
     * @returns {boolean} - Is processing
     */
    MultiFileProcessor.prototype.getIsProcessing = function () {
        return this.isProcessing;
    };

    // Export to global
    global.MultiFileProcessor = MultiFileProcessor;

})(window);
