// The saved Parcel ID's QR code and Code 128 barcode, side by side (invoice, order details, print). Both SVGs are drawn
// by the backend from the order's stored Parcel ID on every request (apps.orders.invoice._codes_svg) — they are never
// the source of truth and never stored. Shapes only, no text nodes, so no user text can reach this markup.
export default function ParcelCodes({ id, qrSvg, barcodeSvg }) {
  if (!id || !qrSvg) return null;
  return (
    <div className="invoice-codes">
      <div className="invoice-code invoice-code--qr" role="img" aria-label={`Parcel ID QR code: ${id}`} dangerouslySetInnerHTML={{ __html: qrSvg }} />
      {barcodeSvg && (
        <div className="invoice-code invoice-code--bar">
          <div role="img" aria-label={`Parcel ID barcode: ${id}`} dangerouslySetInnerHTML={{ __html: barcodeSvg }} />
          <p className="invoice-code__text">{id}</p>
        </div>
      )}
    </div>
  );
}
