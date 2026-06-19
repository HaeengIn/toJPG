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

let pendingFilesArray = [];
let finishedImagesArray = [];

themeBtnElement.addEventListener("click", () => {
  const currentThemeValue =
    rootDocElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");
  if (currentThemeValue === "dark") {
    rootDocElement.setAttribute("data-theme", "light");
  } else {
    rootDocElement.setAttribute("data-theme", "dark");
  }
});

for (let qValue = 0; qValue <= 100; qValue += 10) {
  const optionElement = document.createElement("option");
  optionElement.value = qValue;
  optionElement.textContent = qValue + "%";
  if (qValue === 80) {
    optionElement.selected = true;
  }
  qualitySelectElement.appendChild(optionElement);
}

imageInputElement.addEventListener("change", (evt) => {
  const selectedFiles = evt.target.files;
  for (let idx = 0; idx < selectedFiles.length; idx++) {
    pendingFilesArray.push(selectedFiles[idx]);
  }
  updateFileListView();
  imageInputElement.value = "";
});

clearAllBtnElement.addEventListener("click", () => {
  pendingFilesArray = [];
  updateFileListView();
});

function updateFileListView() {
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
}

convertBtnElement.addEventListener("click", async () => {
  const turnstileTokenValue = document.querySelector(
    '[name="cf-turnstile-response"]',
  )?.value;

  if (!turnstileTokenValue) {
    alert("캡챠 인증을 완료해주세요.");
    return;
  }
  if (pendingFilesArray.length === 0) {
    alert("변환할 이미지를 추가해주세요.");
    return;
  }

  convertBtnElement.textContent = "변환 중...";
  convertBtnElement.disabled = true;

  const formDataObject = new FormData();
  pendingFilesArray.forEach((fileObj) => {
    formDataObject.append("files", fileObj);
  });
  formDataObject.append("quality", qualitySelectElement.value);
  formDataObject.append("cf_turnstile_response", turnstileTokenValue);

  try {
    const serverResponse = await fetch("/convert", {
      method: "POST",
      body: formDataObject,
    });

    if (serverResponse.ok) {
      const responseJson = await serverResponse.json();
      finishedImagesArray = responseJson.images;
      displayConvertedResults();
    } else {
      alert("변환 실패 또는 캡챠 인증 오류가 발생했습니다.");
    }
  } catch (err) {
    alert("서버 통신 중 오류가 발생했습니다.");
  } finally {
    convertBtnElement.textContent = "변환 시작";
    convertBtnElement.disabled = false;
  }
});

function displayConvertedResults() {
  resultAreaElement.style.display = "block";
  convertedListElement.innerHTML = "";

  finishedImagesArray.forEach((imgData) => {
    const liElement = document.createElement("li");
    liElement.textContent = imgData.filename;

    const downloadLinkElement = document.createElement("a");
    downloadLinkElement.href = "data:image/jpeg;base64," + imgData.data;
    downloadLinkElement.download = imgData.filename;
    downloadLinkElement.textContent = "다운로드";
    downloadLinkElement.className = "link-btn";

    liElement.appendChild(downloadLinkElement);
    convertedListElement.appendChild(liElement);
  });
}

downloadZipBtnElement.addEventListener("click", () => {
  if (finishedImagesArray.length === 0) return;

  const zipObject = new JSZip();
  finishedImagesArray.forEach((imgData) => {
    zipObject.file(imgData.filename, imgData.data, { base64: true });
  });

  zipObject.generateAsync({ type: "blob" }).then(function (blobData) {
    const tempAnchorElement = document.createElement("a");
    tempAnchorElement.href = URL.createObjectURL(blobData);
    tempAnchorElement.download = "converted_images.zip";
    tempAnchorElement.click();
  });
});
