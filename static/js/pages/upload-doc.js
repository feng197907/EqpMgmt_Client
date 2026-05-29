/**
 * DMS 多文件上传功能（支持每个文件独立选择类型）
 * 从 upload_doc.html 内联脚本提取
 * 依赖：页面中的 <script type="application/json" id="doc-types-data"> 数据块
 */
const DOC_TYPES = JSON.parse(document.getElementById('doc-types-data').textContent);
const DOC_TYPE_LABELS = {};
DOC_TYPES.forEach(function(pair) { DOC_TYPE_LABELS[pair[0]] = pair[1]; });

var dropzone = document.getElementById('dropzone');
var fileInput = document.getElementById('fileInput');
var dropzoneContent = document.getElementById('dropzoneContent');
var fileList = document.getElementById('fileList');
var addMoreFiles = document.getElementById('addMoreFiles');
var btnAddMore = document.getElementById('btnAddMore');
var submitBtn = document.getElementById('submitBtn');
var defaultDocTypeInput = document.getElementById('defaultDocType');

var selectedFiles = [];

function getDefaultDocType() {
  var checked = document.querySelector('input[name="doc_type_default"]:checked');
  return checked ? checked.value : DOC_TYPES[0][0];
}

// 拖拽效果
['dragenter', 'dragover'].forEach(function(eventName) {
  dropzone.addEventListener(eventName, function(e) {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach(function(eventName) {
  dropzone.addEventListener(eventName, function(e) {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });
});

// 文件选择
fileInput.addEventListener('change', function() {
  addFiles(fileInput.files);
});

dropzone.addEventListener('drop', function(e) {
  var files = e.dataTransfer.files;
  if (files.length > 0) {
    addFiles(files);
  }
});

// 点击添加更多
btnAddMore.addEventListener('click', function(e) {
  e.stopPropagation();
  fileInput.click();
});

function addFiles(files) {
  var defaultType = getDefaultDocType();
  for (var i = 0; i < files.length; i++) {
    selectedFiles.push({
      file: files[i],
      doc_type: defaultType
    });
  }
  syncFileInput();
  renderFileList();
  updateSubmitButton();
}

function removeFileAt(index) {
  selectedFiles.splice(index, 1);
  syncFileInput();
  renderFileList();
  updateSubmitButton();
}

function syncFileInput() {
  var dt = new DataTransfer();
  selectedFiles.forEach(function(item) { dt.items.add(item.file); });
  fileInput.files = dt.files;
}

function buildTypeOptions(selectedValue) {
  return DOC_TYPES.map(function(pair) {
    var value = pair[0];
    var label = pair[1];
    var sel = value === selectedValue ? 'selected' : '';
    return '<option value="' + value + '" ' + sel + '>' + label + '</option>';
  }).join('');
}

function renderFileList() {
  if (selectedFiles.length === 0) {
    dropzoneContent.style.display = 'flex';
    fileList.style.display = 'none';
    addMoreFiles.style.display = 'none';
    dropzone.classList.remove('has-file');
    fileInput.style.pointerEvents = 'auto';
    return;
  }
  dropzoneContent.style.display = 'none';
  fileList.style.display = 'block';
  addMoreFiles.style.display = 'block';
  dropzone.classList.add('has-file');
  fileInput.style.pointerEvents = 'none';

  fileList.innerHTML = '';
  for (var i = 0; i < selectedFiles.length; i++) {
    var item = selectedFiles[i];
    var file = item.file;
    var el = document.createElement('div');
    el.className = 'file-list-item';
    el.innerHTML = '\n      <div class="file-list-icon">\n        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>\n      </div>\n      <div class="file-list-info">\n        <span class="file-list-name">' + escapeHtml(file.name) + '</span>\n        <span class="file-list-size">' + formatFileSize(file.size) + '</span>\n      </div>\n      <div class="file-list-type">\n        <select name="doc_type_per_file_' + i + '" data-index="' + i + '" class="form-select form-select-sm">\n          ' + buildTypeOptions(item.doc_type) + '\n        </select>\n      </div>\n      <button type="button" class="file-list-remove" data-index="' + i + '" title="移除">\n        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>\n      </button>\n    ';
    fileList.appendChild(el);
  }

  // 绑定类型变更
  fileList.querySelectorAll('.form-select').forEach(function(select) {
    select.addEventListener('change', function(e) {
      var idx = parseInt(e.target.dataset.index);
      selectedFiles[idx].doc_type = e.target.value;
    });
  });

  // 绑定移除
  fileList.querySelectorAll('.file-list-remove').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      removeFileAt(parseInt(btn.dataset.index));
    });
  });
}

function updateSubmitButton() {
  var count = selectedFiles.length;
  if (count > 0) {
    submitBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg> 上传 ' + count + ' 个文档';
  } else {
    submitBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg> 上传文档';
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 默认类型选择
var docTypeRadios = document.querySelectorAll('input[name="doc_type_default"]');
docTypeRadios.forEach(function(radio) {
  radio.addEventListener('change', function() {
    defaultDocTypeInput.value = radio.value;
    // 更新校准日期字段显示
    toggleCalibrationField();
    // 新添加的文件会使用新默认值；已添加的文件不自动变更
  });
});

document.querySelectorAll('.doc-type-option').forEach(function(option) {
  option.addEventListener('click', function() {
    document.querySelectorAll('.doc-type-option').forEach(function(o) { o.classList.remove('selected'); });
    option.classList.add('selected');
    option.querySelector('input').checked = true;
    defaultDocTypeInput.value = option.querySelector('input').value;
    toggleCalibrationField();
  });
});

function toggleCalibrationField() {
  var selected = getDefaultDocType();
  var group = document.getElementById('calibrationDueDateGroup');
  if (group) {
    group.style.display = (selected === 'calibration') ? 'block' : 'none';
  }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
  toggleCalibrationField();
});

// 表单提交
var uploadForm = document.getElementById('uploadForm');
uploadForm.addEventListener('submit', function(e) {
  // 构建文件类型映射隐藏字段
  selectedFiles.forEach(function(item, idx) {
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'doc_type_map_' + idx;
    input.value = item.doc_type;
    uploadForm.appendChild(input);
  });
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<svg class="spinner" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/></path></svg> 上传中...';
});
