function startRecording() {
    axios.post('/start_recording')
        .then(function(response) {
            console.log('錄音已開始，正在等待視頻...');
            pollForResultUrl();
        })
        .catch(function(error) {
            console.log('錄音開始失敗:', error);
            document.querySelector('.result').textContent = '錄音開始失敗';
        });
}

function pollForResultUrl() {
    function checkForVideo() {
        axios.get('/get_result_url')
            .then(function(response) {
                if (response.data.result_url) {
                    console.log('獲取到的視頻 URL:', response.data.result_url);
                    var result_video = document.querySelector(".result");
                    result_video.innerHTML = `<video width="640" height="480" controls autoplay>
                        <source src="${response.data.result_url}" type="video/mp4">
                        您的瀏覽器不支援 video 標籤。
                    </video>`;

                    var videoElement = result_video.querySelector("video");
                    videoElement.addEventListener('canplaythrough', event => {
                        videoElement.play(); // 確保影片能夠自動播放
                    });

                    videoElement.addEventListener('ended', () => {
                        console.log('當前影片播放結束，正在請求下一段影片...');
                        setTimeout(checkForVideo, 5000); // 當前影片播完後稍等一秒再請求新影片
                    });

                } else if (response.data.error) {
                    console.log('錯誤訊息:', response.data.error);
                    document.querySelector('.result').innerHTML = '<p>' + response.data.error + '</p>';
                    setTimeout(checkForVideo, 5000); // 如果有錯誤，仍然繼續檢查
                } else {
                    console.log('視頻尚未準備好，再次檢查...');
                    setTimeout(checkForVideo, 5000); // 沒有錯誤但也沒有 URL，繼續檢查
                }
            })
            .catch(function(error) {
                console.log('在獲取結果 URL 時發生錯誤:', error);
                document.querySelector('.result').innerHTML = '<p>獲取視頻失敗</p>';
                setTimeout(checkForVideo, 5000); // 確保即使發生錯誤也能重新嘗試
            });
    }
    checkForVideo(); // 開始第一次檢查
}
