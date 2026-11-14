// CPF e CNPJ, incluindo o CNPJ alfanumerico (letras nas 12 primeiras posicoes).

export function normalizeDocument(value: string): string {
  return value.replace(/[^0-9a-zA-Z]/g, "").toUpperCase();
}

function isValidCpf(digits: string): boolean {
  if (!/^\d{11}$/.test(digits) || /^(\d)\1{10}$/.test(digits)) return false;
  const check = (length: number) => {
    let sum = 0;
    for (let i = 0; i < length; i += 1) sum += Number(digits[i]) * (length + 1 - i);
    const rest = (sum * 10) % 11;
    return rest === 10 ? 0 : rest;
  };
  return check(9) === Number(digits[9]) && check(10) === Number(digits[10]);
}

function isValidCnpj(value: string): boolean {
  if (!/^[0-9A-Z]{12}\d{2}$/.test(value) || /^(.)\1{13}$/.test(value)) return false;
  // Cada caractere vale o codigo ASCII menos 48: digitos seguem 0-9, letras A=17...Z=42.
  const values = [...value].map((char) => char.charCodeAt(0) - 48);
  const check = (length: number) => {
    let sum = 0;
    let weight = 2;
    for (let i = length - 1; i >= 0; i -= 1) {
      sum += values[i] * weight;
      weight = weight === 9 ? 2 : weight + 1;
    }
    const rest = sum % 11;
    return rest < 2 ? 0 : 11 - rest;
  };
  return check(12) === values[12] && check(13) === values[13];
}

export function isValidCpfCnpj(value: string): boolean {
  const normalized = normalizeDocument(value);
  return normalized.length === 11 ? isValidCpf(normalized) : isValidCnpj(normalized);
}

export function formatDocument(value: string | null): string {
  if (!value) return "";
  const normalized = normalizeDocument(value);
  if (/^\d{11}$/.test(normalized)) {
    return normalized.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
  }
  if (/^[0-9A-Z]{12}\d{2}$/.test(normalized)) {
    return normalized.replace(/^(.{2})(.{3})(.{3})(.{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  }
  return value;
}
