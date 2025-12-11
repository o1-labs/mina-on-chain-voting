export class SafeFetchError extends Error {
  constructor(public readonly url: string, public readonly status: number, public readonly statusText: string) {
    super(`safeFetch request to ${url} failed with message ${status} - ${statusText}`);
  }
}

export const safeFetch = async (
  endpoint: string,
  requestOptions?: RequestInit,
  responseType: 'json' | 'text' = 'json'
) => {
  const url = new URL(process.env.NEXT_PUBLIC_API_BASE_URL + endpoint);
  const response = await fetch(url, {
    ...requestOptions,
    cache: 'no-store',
    next: { revalidate: 0 }
  });

  if (!response.ok) {
    console.log('---------------------------');
    console.log(response);
    // ✅ READ THE ERROR BODY
    const errorBody = await response.text();
    console.log('Error body:', errorBody);
    throw new SafeFetchError(response.url, response.status, response.statusText);
  }

  return await response[responseType]();
};
