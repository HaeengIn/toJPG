const rootDocElement = document.documentElement;
const themeBtnElement = document.getElementById("themeToggleBtn");
const qualitySelectElement = document.getElementById("qualitySelect");
const imageInputElement = document.getElementById("imageInput");
const fileListElement = document.getElementById("fileListContainer");
const clearAllBtnElement = document.getElementById("clearAllBtn");
const convertBtnElement = document.getElementById("convertSubmitBtn");
const resultAreaElement = document.getElementById("conversionResultArea");
const convertedListElement = document.getElementById("convertedListContainer");
const downloadZipBtnElement = document.getElementById("downloadZipBtn");
const clearResultsBtnElement = document.getElementById("clearResultsBtn");

const MAX_UPLOAD_FILES = 200;
const MAX_UPLOAD_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_UPLOAD_TOTAL_SIZE = 100 * 1024 * 1024; // 100MB

const fileSummaryElement = document.getElementById("fileSummary");
let pendingFilesArray = [];
let finishedImagesArray = [];

const setSubmitState = (isSubmitting) => {
  convertBtnElement.textContent = isSubmitting ? "변환 중..." : "변환 시작";
  convertBtnElement.disabled = isSubmitting;
};

const buildQualityOptions = () => {
  for (let qValue = 0; qValue <= 100; qValue += 10) {
    const optionElement = document.createElement("option");
    optionElement.value = qValue;
    optionElement.textContent = `${qValue}%`;
    if (qValue === 80) optionElement.selected = true;
    qualitySelectElement.appendChild(optionElement);
  }
};

const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const updateFileListView = () => {
  fileListElement.innerHTML = "";
  pendingFilesArray.forEach((fileObj, arrIndex) => {
    const liElement = document.createElement("li");
    liElement.textContent = fileObj.name;

    const deleteBtnElement = document.createElement("button");
    deleteBtnElement.textContent = "삭제";
    deleteBtnElement.className = "btn-danger";
    deleteBtnElement.addEventListener("click", () => {
      pendingFilesArray.splice(arrIndex, 1);
      updateFileListView();
    });

    liElement.appendChild(deleteBtnElement);
    fileListElement.appendChild(liElement);
  });

  const totalSize = pendingFilesArray.reduce((sum, file) => sum + file.size, 0);
  fileSummaryElement.textContent = `선택된 파일: ${pendingFilesArray.length}개, 총 용량: ${formatBytes(totalSize)}`;
};

const displayConvertedResults = () => {
  if (finishedImagesArray.length === 0) {
    clearConvertedResults();
    return;
  }

  resultAreaElement.style.display = "block";
  convertedListElement.innerHTML = "";

  finishedImagesArray.forEach((imgData, index) => {
    const liElement = document.createElement("li");
    const textWrapper = document.createElement("span");
    textWrapper.textContent = imgData.filename;

    const actionsWrapper = document.createElement("div");
    actionsWrapper.style.display = "flex";
    actionsWrapper.style.gap = "8px";
    actionsWrapper.style.alignItems = "center";

    const downloadLinkElement = document.createElement("a");
    downloadLinkElement.href = `data:image/jpeg;base64,${imgData.data}`;
    downloadLinkElement.download = imgData.filename;
    downloadLinkElement.textContent = "다운로드";
    downloadLinkElement.className = "link-btn";

    const deleteBtnElement = document.createElement("button");
    deleteBtnElement.textContent = "삭제";
    deleteBtnElement.className = "btn-danger";
    deleteBtnElement.addEventListener("click", () =>
      removeConvertedImage(index),
    );

    actionsWrapper.appendChild(downloadLinkElement);
    actionsWrapper.appendChild(deleteBtnElement);
    liElement.appendChild(textWrapper);
    liElement.appendChild(actionsWrapper);
    convertedListElement.appendChild(liElement);
  });
};

const showAlert = (message) => {
  window.alert(message);
};

const resetTurnstile = () => {
  if (window.turnstile) {
    window.turnstile.reset();
  }
};

const clearConvertedResults = () => {
  finishedImagesArray = [];
  convertedListElement.innerHTML = "";
  resultAreaElement.style.display = "none";
};

const removeConvertedImage = (index) => {
  finishedImagesArray.splice(index, 1);
  if (finishedImagesArray.length === 0) {
    clearConvertedResults();
    return;
  }
  displayConvertedResults();
};

themeBtnElement.addEventListener("click", () => {
  const currentThemeValue =
    rootDocElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");
  rootDocElement.setAttribute(
    "data-theme",
    currentThemeValue === "dark" ? "light" : "dark",
  );
});

imageInputElement.addEventListener("change", (event) => {
  const selectedFiles = Array.from(event.target.files || []);

  if (pendingFilesArray.length + selectedFiles.length > MAX_UPLOAD_FILES) {
    showAlert(`최대 업로드 개수는 ${MAX_UPLOAD_FILES}개입니다.`);
    imageInputElement.value = "";
    return;
  }

  const oversizedFile = selectedFiles.find(
    (file) => file.size > MAX_UPLOAD_FILE_SIZE,
  );
  if (oversizedFile) {
    showAlert(
      `"${oversizedFile.name}" 파일 크기가 너무 큽니다. 최대 ${
        MAX_UPLOAD_FILE_SIZE / (1024 * 1024)
      }MB까지 업로드 가능합니다.`,
    );
    imageInputElement.value = "";
    return;
  }

  pendingFilesArray.push(...selectedFiles);
  updateFileListView();
  imageInputElement.value = "";
});

clearAllBtnElement.addEventListener("click", () => {
  pendingFilesArray = [];
  updateFileListView();
});

convertBtnElement.addEventListener("click", async () => {
  const turnstileTokenValue = document.querySelector(
    '[name="cf-turnstile-response"]',
  )?.value;

  if (!turnstileTokenValue) {
    showAlert("캡챠 인증을 완료해주세요.");
    return;
  }

  if (pendingFilesArray.length === 0) {
    showAlert("변환할 이미지를 추가해주세요.");
    return;
  }

  setSubmitState(true);

  const formDataObject = new FormData();
  pendingFilesArray.forEach((fileObj) =>
    formDataObject.append("files", fileObj),
  );
  formDataObject.append("quality", qualitySelectElement.value);
  formDataObject.append("cf_turnstile_response", turnstileTokenValue);

  try {
    const serverResponse = await fetch("/convert", {
      method: "POST",
      body: formDataObject,
    });

    if (!serverResponse.ok) {
      const errorText = await serverResponse.text();
      throw new Error(
        errorText || "변환 실패 또는 캡챠 인증 오류가 발생했습니다.",
      );
    }

    const responseJson = await serverResponse.json();
    finishedImagesArray = responseJson.images || [];
    displayConvertedResults();
  } catch (error) {
    showAlert(error.message || "서버 통신 중 오류가 발생했습니다.");
  } finally {
    resetTurnstile();
    setSubmitState(false);
  }
});

downloadZipBtnElement.addEventListener("click", () => {
  if (finishedImagesArray.length === 0) return;

  const zipObject = new JSZip();
  finishedImagesArray.forEach((imgData) => {
    zipObject.file(imgData.filename, imgData.data, { base64: true });
  });

  zipObject.generateAsync({ type: "blob" }).then((blobData) => {
    const tempAnchorElement = document.createElement("a");
    tempAnchorElement.href = URL.createObjectURL(blobData);
    tempAnchorElement.download = "converted_toJPG.zip";
    tempAnchorElement.click();
  });
});

clearResultsBtnElement.addEventListener("click", clearConvertedResults);

buildQualityOptions();
