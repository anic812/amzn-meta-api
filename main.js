const obj = {};

const badgeMap = {
  sdAvailable: "https://img.shields.io/badge/SD-8A2BE2?style=plastic",
  hdAvailable: "https://img.shields.io/badge/HD-8A2BE?style=plastic",
  uhdAvailable: "https://img.shields.io/badge/UHD-ecad0a?style=plastic",
  atmosAvailable:
    "https://img.shields.io/badge/Dolby%20Atmos-blue?style=plastic",
  immersive: "https://img.shields.io/badge/3D-808080?style=plastic",
};
const titleElements = document.querySelectorAll(".title");
titleElements.forEach((element) => {
  element.textContent = obj.title;
});

document.body.style.backgroundImage = `url('${
  obj.artwork_hires || obj.artwork_standard
}')`;
document.getElementById("img-dis").src = obj.artwork;
document.getElementById("hi-resArt").href = obj.artwork_hires;
document.getElementById("artist").innerText = obj.artist_name;
document.getElementById("alb_asin").innerText = obj.asin;
document.getElementById("rel_date").innerText = obj.original_release_date.slice(
  0,
  10
);
document.getElementById("dur").innerText = obj.duration;
document.getElementById("cpyr").innerText = obj.copyright;
document.getElementById("rate").innerText = obj.price;
document.getElementById("lbl").innerText = obj.label;
obj.content_encoding.forEach(
  (value) =>
    badgeMap[value] &&
    document
      .getElementById("badgeEncoding")
      .insertAdjacentHTML(
        "beforeend",
        `<img style="margin-left: 5px;" src="${badgeMap[value]}" alt="${value} badge">`
      )
);

function downloadLyrics(filename, lyrics) {
    const blob = new Blob([lyrics], { type: "text/plain;charset=utf-8" });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
}


const tbody = document.getElementById('track-list');
tbody.innerHTML = obj.tracks.map(track => `
    <tr>
        <td>${track.track_num}</td>
        <td><b>${track.title}</b> ${ track.lyrics.length > 10 ? `<div style="cursor: pointer; text-decoration: underline;" class="ml-2 badge text-bg-success" onclick="downloadLyrics('${track.track_num}.${track.title}.lrc', \`${track.lyrics.replace(/`/g, '\\`')}\`)">🎶</div>` : ''}${track.artist !== obj.artist_name ? `<br> ${track.artist}` : ''}</td>
        <td>${track.duration}</td>
    </tr>
`).join('');
