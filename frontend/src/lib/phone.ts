// Telefones brasileiros: (DD) NNNN-NNNN para fixo e (DD) NNNNN-NNNN para celular.

export function phoneDigits(value: string | null): string {
  let digits = (value ?? "").replace(/\D/g, "");
  // Aceita colagem com codigo do pais (+55) ou zero de operadora antes do DDD.
  if (digits.length > 11 && digits.startsWith("55")) digits = digits.slice(2);
  if (digits.length > 10 && digits.startsWith("0")) digits = digits.slice(1);
  return digits.slice(0, 11);
}

export function formatPhone(value: string | null): string {
  const digits = phoneDigits(value);
  if (digits.length === 0) return "";
  if (digits.length <= 2) return `(${digits}`;
  const area = digits.slice(0, 2);
  const number = digits.slice(2);
  if (number.length <= 4) return `(${area}) ${number}`;
  const split = number.length === 9 ? 5 : 4;
  return `(${area}) ${number.slice(0, split)}-${number.slice(split)}`;
}

export function isCompletePhone(value: string | null): boolean {
  const { length } = phoneDigits(value);
  return length === 10 || length === 11;
}
