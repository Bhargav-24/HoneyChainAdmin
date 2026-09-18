const hiveSelect = document.querySelector('#hive-select');
const hiveSummary = document.querySelector('#hive-summary');
const sensorForm = document.querySelector('#sensor-form');
const formMessage = document.querySelector('#form-message');
const updateButton = document.querySelector('.update-button');

const controls = [
  { id: 'temperature', output: 'temperature-value', format: (value) => `${Number(value).toFixed(1)} °C` },
  { id: 'humidity', output: 'humidity-value', format: (value) => `${value} %` },
  { id: 'co2', output: 'co2-value', format: (value) => `${value} ppm` },
  { id: 'weight', output: 'weight-value', format: (value) => `${Number(value).toFixed(1)} kg` },
  { id: 'sound', output: 'sound-value', format: (value) => value },
  { id: 'bee-count', output: 'bee-count-value', format: (value) => Number(value).toLocaleString() },
];

const setMessage = (message, isError = false) => {
  formMessage.textContent = message;
  formMessage.classList.toggle('error', isError);
};

const updateValue = ({ id, output, format }) => {
  document.querySelector(`#${output}`).textContent = format(document.querySelector(`#${id}`).value);
};

controls.forEach((control) => {
  const input = document.querySelector(`#${control.id}`);
  input.addEventListener('input', () => updateValue(control));
  updateValue(control);
});

const renderHiveSummary = () => {
  const hive = [...hiveSelect.options].find((option) => option.value === hiveSelect.value)?.dataset;
  if (!hive) {
    hiveSummary.textContent = 'Select a hive to see its details.';
    return;
  }
  hiveSummary.textContent = `${hive.location || 'Location not supplied'} · ${hive.species || 'Species not supplied'} · ${hive.type || 'Hive type not supplied'} · Status: ${hive.status || 'Unknown'}`;
};

const loadHives = async () => {
  const response = await fetch('/api/iot/hives');
  if (!response.ok) throw new Error('Registered hives could not be loaded.');
  const hives = await response.json();
  hiveSelect.replaceChildren();
  hives.forEach((hive) => {
    const option = document.createElement('option');
    option.value = hive.hive_id;
    option.textContent = hive.hive_id;
    option.dataset.location = hive.location || '';
    option.dataset.species = hive.bee_species || '';
    option.dataset.type = hive.hive_type || '';
    option.dataset.status = hive.status || '';
    hiveSelect.appendChild(option);
  });
  if (!hives.length) {
    const option = document.createElement('option');
    option.textContent = 'No registered hives';
    option.value = '';
    hiveSelect.appendChild(option);
  }
  renderHiveSummary();
};

hiveSelect.addEventListener('change', renderHiveSummary);
sensorForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!hiveSelect.value) {
    setMessage('Select a hive first.', true);
    return;
  }
  updateButton.disabled = true;
  setMessage('Saving reading...');
  const payload = Object.fromEntries(controls.map(({ id }) => [id.replace('-', '_'), Number(document.querySelector(`#${id}`).value)]));
  try {
    const response = await fetch(`/api/iot/hives/${encodeURIComponent(hiveSelect.value)}/readings`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || 'The reading could not be saved.');
    setMessage(`Reading saved at ${new Date(result.recorded_at).toLocaleTimeString()}.`);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    updateButton.disabled = false;
  }
});

loadHives().catch((error) => setMessage(error.message, true));
